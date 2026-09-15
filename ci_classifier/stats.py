"""Statistics for comparing classifiers on the same samples.

- Confidence intervals use a cluster bootstrap: whole (repo, workflow) groups are resampled, because runs
  of one workflow have near-identical logs and are not independent samples.
- McNemar's exact test compares two classifiers on the samples where exactly one of them is right.
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

import numpy as np

from .common import UNKNOWN


def accuracy(y_true: np.ndarray, y_pred: np.ndarray, categories: Sequence[str]) -> float:
    return float(np.mean(y_true == y_pred)) if len(y_true) else math.nan


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, categories: Sequence[str]) -> float:
    """Mean F1 over categories present in y_true; same definition as evaluate.compute_metrics."""
    scores = []
    for category in categories:
        support = np.sum(y_true == category)
        if support == 0:
            continue
        true_pos = np.sum((y_true == category) & (y_pred == category))
        predicted = np.sum(y_pred == category)
        precision = true_pos / predicted if predicted else 0.0
        recall = true_pos / support
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return float(np.mean(scores)) if scores else math.nan


def abstention(y_true: np.ndarray, y_pred: np.ndarray, categories: Sequence[str]) -> float:
    return float(np.mean(y_pred == UNKNOWN)) if len(y_pred) else math.nan


Metric = Callable[[np.ndarray, np.ndarray, Sequence[str]], float]


def group_bootstrap_ci(y_true: Sequence[str], y_pred: Sequence[str], groups: Sequence[str], metric: Metric,
                       categories: Sequence[str], samples: int = 1000, seed: int = 42,
                       level: float = 0.95) -> tuple[float, float, float]:
    """Return (point estimate, lower, upper) of `metric`, resampling whole groups with replacement."""
    y_true, y_pred, groups = np.asarray(y_true), np.asarray(y_pred), np.asarray(groups)
    point = metric(y_true, y_pred, categories)
    unique = np.unique(groups)
    members = [np.flatnonzero(groups == g) for g in unique]
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(samples):
        chosen = rng.integers(0, len(unique), len(unique))
        index = np.concatenate([members[i] for i in chosen])
        estimates.append(metric(y_true[index], y_pred[index], categories))
    alpha = (1 - level) / 2
    lower, upper = np.nanquantile(estimates, [alpha, 1 - alpha])
    return point, float(lower), float(upper)


def mcnemar_exact(correct_a: Sequence[bool], correct_b: Sequence[bool]) -> dict:
    """Exact two-sided McNemar test. `a_only` = A right and B wrong, `b_only` = the reverse."""
    correct_a, correct_b = np.asarray(correct_a, bool), np.asarray(correct_b, bool)
    a_only = int(np.sum(correct_a & ~correct_b))
    b_only = int(np.sum(~correct_a & correct_b))
    n = a_only + b_only
    if n == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(n, k) for k in range(min(a_only, b_only) + 1)) / 2 ** n
        p_value = min(1.0, 2 * tail)
    return {"a_only": a_only, "b_only": b_only, "p_value": p_value}
