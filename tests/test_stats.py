import math

import numpy as np
import pytest

from ci_classifier import stats
from ci_classifier.evaluate import compute_metrics

CATS = ["compilation", "test_assertion", "other"]


def test_macro_f1_matches_compute_metrics():
    y_true = ["compilation", "compilation", "test_assertion", "other", "other"]
    y_pred = ["compilation", "unknown", "compilation", "other", "test_assertion"]
    expected = compute_metrics(y_true, y_pred, CATS)["summary"]["macro_f1"]
    assert stats.macro_f1(np.array(y_true), np.array(y_pred), CATS) == pytest.approx(expected)


def test_group_bootstrap_ci_contains_point_and_is_degenerate_when_all_correct():
    y_true = ["other"] * 6 + ["compilation"] * 6
    y_pred = ["other"] * 6 + ["compilation"] * 3 + ["unknown"] * 3
    groups = ["g1", "g1", "g2", "g2", "g3", "g3", "g4", "g4", "g5", "g5", "g6", "g6"]
    point, low, high = stats.group_bootstrap_ci(y_true, y_pred, groups, stats.accuracy, CATS, samples=500)
    assert point == pytest.approx(0.75)
    assert low <= point <= high and low < high

    point, low, high = stats.group_bootstrap_ci(y_true, y_true, groups, stats.accuracy, CATS, samples=50)
    assert (point, low, high) == (1.0, 1.0, 1.0)


def test_group_bootstrap_is_reproducible():
    args = (["other", "compilation"] * 5, ["other", "unknown"] * 5, [f"g{i % 4}" for i in range(10)],
            stats.accuracy, CATS)
    assert stats.group_bootstrap_ci(*args, samples=200, seed=7) == stats.group_bootstrap_ci(*args, samples=200, seed=7)


def test_mcnemar_exact():
    # 10 discordant pairs, all favouring A: p = 2 * 0.5^10
    result = stats.mcnemar_exact([True] * 10 + [True] * 5, [False] * 10 + [True] * 5)
    assert (result["a_only"], result["b_only"]) == (10, 0)
    assert result["p_value"] == pytest.approx(2 / 1024)

    balanced = stats.mcnemar_exact([True, False, True, False], [False, True, False, True])
    assert balanced["p_value"] == 1.0
    assert stats.mcnemar_exact([True], [True])["p_value"] == 1.0
    assert not math.isnan(stats.mcnemar_exact([True, False], [False, False])["p_value"])
