import pandas as pd
import pytest

from ci_classifier import tune_tfidf
from ci_classifier.common import UNKNOWN


def test_threshold_table_turns_low_probabilities_into_unknown():
    answers = [("a", 0.9), ("b", 0.3), ("a", 0.3)]
    table = tune_tfidf.threshold_table(answers, ["a", "b", "b"], ["a", "b"], [0.0, 0.5]).set_index("threshold")
    assert table.loc[0.0, "accuracy"] == pytest.approx(2 / 3)
    assert table.loc[0.0, "abstention"] == 0
    assert table.loc[0.5, "accuracy"] == pytest.approx(1 / 3)
    assert table.loc[0.5, "abstention"] == pytest.approx(2 / 3)
    assert table.loc[0.5, "accuracy_when_answered"] == 1.0


def test_choose_prefers_highest_tied_threshold_or_precision_target():
    table = pd.DataFrame({"threshold": [0.0, 0.2, 0.4], "accuracy": [0.6, 0.6, 0.3],
                          "accuracy_when_answered": [0.6, 0.6, 0.9]})
    assert tune_tfidf.choose(table) == 0.2
    assert tune_tfidf.choose(table, min_precision=0.8) == 0.4
    assert tune_tfidf.choose(table, min_precision=0.95) is None


def test_out_of_fold_predicts_every_sample():
    texts, y, groups = [], [], []
    for g in range(6):
        for label, text in (("compilation", "error CS1002 Build FAILED"), ("dependency", "npm ERR! ERESOLVE")):
            texts.append(f"{text} run {g}")
            y.append(label)
            groups.append(f"repo{g}::{label}")
    answers = tune_tfidf.out_of_fold(texts, y, groups, y, folds=3, seed=1)
    assert [category for category, _ in answers] == y
    assert all(UNKNOWN != category for category, _ in answers)
