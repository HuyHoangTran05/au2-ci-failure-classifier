"""Grouped, stratified k-fold cross-validation over all labelled samples.

Each fold keeps whole (repo, workflow) groups together (as `split` does) and balances (source, label).
Keyword rules need no training; TF-IDF is refitted on the other folds; the LLM needs no training and is scored
from stored answers only, so in each fold it covers just the samples already sent to the API.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from . import llm, rules, stats
from .common import read_excerpt
from .split import group_of
from .tfidf import TfidfClassifier


def cross_validate(sample_ids: list[str], labels: dict[str, dict], manifest: dict[str, dict], config: dict,
                   folds: int, seed: int, excerpts: dict[str, str] | None = None) -> pd.DataFrame:
    """Return one row per (fold, method) with the samples scored and their metrics."""
    categories = config["categories"]
    sample_ids = sorted(sample_ids)
    excerpts = excerpts or {sid: read_excerpt(sid) for sid in sample_ids}
    y = np.array([labels[sid]["label"] for sid in sample_ids])
    strata = [f"{manifest[sid].get('source', 'github-actions')}:{labels[sid]['label']}" for sid in sample_ids]
    groups = [group_of(manifest[sid]) for sid in sample_ids]
    llm_predict = llm.cached_predictor(config)

    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    rows = []
    with warnings.catch_warnings():
        # Rare (source, label) strata have fewer members than folds; sklearn warns but still splits.
        warnings.filterwarnings("ignore", message="The least populated class")
        fold_indices = list(splitter.split(sample_ids, strata, groups))

    for fold, (train_idx, test_idx) in enumerate(fold_indices, start=1):
        test_ids = [sample_ids[i] for i in test_idx]
        texts = [excerpts[sid] for sid in test_ids]
        y_test = y[test_idx]

        model = TfidfClassifier(config["tfidf"]["abstain_below"])
        model.fit([excerpts[sample_ids[i]] for i in train_idx], list(y[train_idx]))
        predictions = {
            "rules": [rules.classify(text)[0] for text in texts],
            "tfidf": [category for category, _ in model.predict(texts)],
            "llm": [(answer[0] if answer else None) for answer in map(llm_predict, texts)],
        }
        for method, predicted in predictions.items():
            scored = np.array([p is not None for p in predicted])
            if not scored.any():
                continue
            y_true, y_pred = y_test[scored], np.array([p for p in predicted if p is not None])
            rows.append({
                "fold": fold, "method": method, "test_samples": len(test_ids), "scored": int(scored.sum()),
                "accuracy": stats.accuracy(y_true, y_pred, categories),
                "macro_f1": stats.macro_f1(y_true, y_pred, categories),
                "abstention": stats.abstention(y_true, y_pred, categories),
            })
    return pd.DataFrame(rows)


def summarize(folds: pd.DataFrame) -> pd.DataFrame:
    """Mean and standard deviation across folds, per method."""
    return folds.groupby("method", sort=False).agg(
        folds=("fold", "nunique"), scored=("scored", "sum"),
        accuracy_mean=("accuracy", "mean"), accuracy_std=("accuracy", "std"),
        macro_f1_mean=("macro_f1", "mean"), macro_f1_std=("macro_f1", "std"),
        abstention_mean=("abstention", "mean"),
    )
