"""Build a predictor for each classification method from the labelled train set."""

from __future__ import annotations

from typing import Callable

from . import llm, rules
from .common import read_excerpt
from .tfidf import TfidfClassifier

METHODS = ["rules", "tfidf", "llm"]
# A predictor returns None only when it has no answer for a sample (an LLM sample not yet sent to the API).
Predictor = Callable[[str], tuple[str, str] | None]


def build_predictor(method: str, config: dict, labels: dict[str, dict], split: dict | None,
                    live: bool = False) -> Predictor:
    """Return a function mapping excerpt text to (category, detail).

    For "llm", the default predictor reads stored answers only; `live=True` calls the API for unseen text.
    Raises ValueError when the method cannot be built (e.g. TF-IDF without labelled train data).
    """
    if method == "rules":
        return rules.classify
    if method == "tfidf":
        if split is None:
            raise ValueError("TF-IDF needs data/split.json; run `python -m ci_classifier split` first")
        train_ids = [sid for sid in split["train"] if sid in labels]
        model = TfidfClassifier(config["tfidf"]["abstain_below"])
        model.fit([read_excerpt(sid) for sid in train_ids], [labels[sid]["label"] for sid in train_ids])

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
    raise ValueError(f"unknown method {method!r}; choose from {', '.join(METHODS)}")
