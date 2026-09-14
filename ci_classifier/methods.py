"""Build a predictor for each classification method from the labelled train set."""

from __future__ import annotations

from typing import Callable

from . import rules
from .common import read_excerpt
from .tfidf import TfidfClassifier

METHODS = ["rules", "tfidf"]
Predictor = Callable[[str], tuple[str, str]]


def build_predictor(method: str, config: dict, labels: dict[str, dict], split: dict | None) -> Predictor:
    """Return a function mapping excerpt text to (category, detail).

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
    raise ValueError(f"unknown method {method!r}; choose from {', '.join(METHODS)}")
