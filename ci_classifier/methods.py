"""Build a predictor for each classification method from the labelled train set."""

from __future__ import annotations

from typing import Callable

from . import llm, rules
from .common import UNKNOWN, read_excerpt
from .tfidf import TfidfClassifier

METHODS = ["rules", "tfidf", "llm", "hybrid"]
# A predictor returns None only when it has no answer for a sample (an LLM sample not yet sent to the API).
Predictor = Callable[[str], tuple[str, str] | None]


def with_fallback(primary: Predictor, fallback: Predictor, name: str = "tfidf") -> Predictor:
    """Use `primary`, and ask `fallback` only when primary answers "unknown".

    A sample primary has no answer for stays unanswered, so the combination is scored on the same samples.
    """
    def predict(text: str) -> tuple[str, str] | None:
        answer = primary(text)
        if answer is None or answer[0] != UNKNOWN:
            return answer
        backup = fallback(text)
        if backup is None:
            return answer
        return backup[0], f"{name} fallback {backup[1]} (primary: {answer[1]})"

    return predict


def fit_tfidf(config: dict, labels: dict[str, dict], split: dict | None) -> TfidfClassifier:
    if split is None:
        raise ValueError("TF-IDF needs data/split.json; run `python -m ci_classifier split` first")
    train_ids = [sid for sid in split["train"] if sid in labels]
    model = TfidfClassifier(config["tfidf"]["abstain_below"])
    return model.fit([read_excerpt(sid) for sid in train_ids], [labels[sid]["label"] for sid in train_ids])


def build_predictor(method: str, config: dict, labels: dict[str, dict], split: dict | None,
                    live: bool = False) -> Predictor:
    """Return a function mapping excerpt text to (category, detail).

    For "llm" and "hybrid", the default predictor reads stored answers only; `live=True` calls the API for unseen
    text. "hybrid" is the LLM with TF-IDF answering whenever the LLM abstains.
    Raises ValueError when the method cannot be built (e.g. TF-IDF without labelled train data).
    """
    if method == "rules":
        return rules.classify
    if method == "tfidf":
        model = fit_tfidf(config, labels, split)

        def predict(text: str) -> tuple[str, str]:
            category, probability = model.predict([text])[0]
            return category, f"p={probability:.2f}"

        return predict
    if method == "llm":
        cached = llm.cached_predictor(config)
        if not live:
            return cached
        try:
            client = llm.OpenRouterClient(config["llm"], llm.load_api_key())
        except llm.LLMError as exc:
            raise ValueError(str(exc)) from exc

        def predict_live(text: str) -> tuple[str, str]:
            answer = cached(text)
            if answer is not None:
                return answer
            try:
                record = llm.classify_text(text, config, client)
            except llm.LLMError as exc:
                raise ValueError(f"LLM call failed: {exc}") from exc
            return llm.to_prediction(record, config["llm"]["abstain_below"])

        return predict_live
    if method == "hybrid":
        return with_fallback(build_predictor("llm", config, labels, split, live),
                             build_predictor("tfidf", config, labels, split))
    raise ValueError(f"unknown method {method!r}; choose from {', '.join(METHODS)}")
