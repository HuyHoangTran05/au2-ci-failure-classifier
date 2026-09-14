"""Baseline 2: text similarity (TF-IDF features + logistic regression)."""

from __future__ import annotations

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from .common import UNKNOWN

GUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
HEX = re.compile(r"\b[0-9a-f]{12,}\b", re.IGNORECASE)
PATH = re.compile(r"(?:[A-Za-z]:)?(?:[\\/][\w.@+-]+){2,}")
NUMBER = re.compile(r"\b\d+(?:\.\d+)*\b")


def normalize(text: str) -> str:
    """Replace run-specific values so logs from different runs share vocabulary."""
    text = GUID.sub(" guid ", text)
    text = HEX.sub(" hex ", text)
    # Keep the file name: "page-route.spec.ts" says more than the directory it sits in.
    text = PATH.sub(lambda m: " path " + re.split(r"[\\/]", m.group())[-1] + " ", text)
    text = NUMBER.sub(" num ", text)
    return text.lower()


class TfidfClassifier:
    def __init__(self, abstain_below: float):
        self.abstain_below = abstain_below
        self.pipeline = make_pipeline(
            TfidfVectorizer(
                preprocessor=normalize,
                token_pattern=r"[a-z_][a-z0-9_]+",
                ngram_range=(1, 2),
                sublinear_tf=True,
                max_features=50_000,
            ),
            LogisticRegression(max_iter=2000, class_weight="balanced"),
        )

    def fit(self, texts: list[str], labels: list[str]) -> "TfidfClassifier":
        if len(set(labels)) < 2:
            raise ValueError("TF-IDF needs at least two different labels in the train set")
        self.pipeline.fit(texts, labels)
        return self

    def predict(self, texts: list[str]) -> list[tuple[str, float]]:
        """Return (category, probability); category is "unknown" when below the abstain threshold."""
        classes = self.pipeline.classes_
        results = []
        for row in self.pipeline.predict_proba(texts):
            best = row.argmax()
            label = str(classes[best]) if row[best] >= self.abstain_below else UNKNOWN
            results.append((label, float(row[best])))
        return results
