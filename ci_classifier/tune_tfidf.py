"""Choose the TF-IDF abstain threshold with grouped cross-validation on the train set only.

The model is refitted on each fold's other groups; every candidate threshold is then applied to the same
out-of-fold probabilities. By default the chosen threshold maximises accuracy ("unknown" counts as wrong),
taking the highest threshold when several tie. With --min-precision, it is the lowest threshold whose
accuracy-when-answered reaches the target (most answers that meet the precision target).

The test set is never read. Copy the chosen value into config.toml [tfidf] abstain_below.

Usage:
    python -m ci_classifier tune-tfidf
    python -m ci_classifier tune-tfidf --min-precision 0.8
"""

from __future__ import annotations

import argparse
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from . import stats
from .common import RESULTS, UNKNOWN, excerpt_profile, load_config, read_excerpt, read_labels, read_manifest, read_split
from .split import group_of
from .tfidf import TfidfClassifier

THRESHOLDS = [0.0, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6]


def out_of_fold(texts: list[str], y: list[str], groups: list[str], strata: list[str],
                folds: int, seed: int) -> list[tuple[str, float]]:
    """(best category, its probability) for every sample, from a model that never saw the sample's group."""
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="The least populated class")
        fold_indices = list(splitter.split(texts, strata, groups))
    result: list[tuple[str, float] | None] = [None] * len(texts)
    for train_idx, test_idx in fold_indices:
        model = TfidfClassifier(0.0).fit([texts[i] for i in train_idx], [y[i] for i in train_idx])
        for i, answer in zip(test_idx, model.predict([texts[i] for i in test_idx])):
            result[i] = answer
    return result  # type: ignore[return-value]


def threshold_table(answers: list[tuple[str, float]], y: list[str], categories: list[str],
                    thresholds: list[float]) -> pd.DataFrame:
    y_true = np.array(y)
    rows = []
    for threshold in thresholds:
        y_pred = np.array([category if probability >= threshold else UNKNOWN for category, probability in answers])
        answered = y_pred != UNKNOWN
        rows.append({
            "threshold": threshold,
            "accuracy": stats.accuracy(y_true, y_pred, categories),
            "abstention": 1 - answered.mean(),
            "accuracy_when_answered": float(np.mean(y_true[answered] == y_pred[answered])) if answered.any() else np.nan,
            "macro_f1": stats.macro_f1(y_true, y_pred, categories),
        })
    return pd.DataFrame(rows)


def choose(table: pd.DataFrame, min_precision: float | None = None) -> float | None:
    """Threshold to use, or None when no threshold meets the precision target."""
    if min_precision is not None:
        meeting = table[table["accuracy_when_answered"] >= min_precision]
        return None if meeting.empty else float(meeting["threshold"].min())
    best = table["accuracy"].round(6).max()
    return float(table.loc[table["accuracy"].round(6) == best, "threshold"].max())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier tune-tfidf", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--min-precision", type=float, default=None,
                        help="pick the lowest threshold whose accuracy when answered reaches this value")
    args = parser.parse_args(argv)

    config = load_config()
    labels, manifest, split = read_labels(), read_manifest(), read_split()
    if split is None:
        parser.error("no data/split.json yet; run `python -m ci_classifier split` first")
    train_ids = sorted(sid for sid in split["train"] if sid in labels)
    y = [labels[sid]["label"] for sid in train_ids]
    answers = out_of_fold([read_excerpt(sid) for sid in train_ids], y,
                          [group_of(manifest[sid]) for sid in train_ids],
                          [f"{manifest[sid].get('source', 'github-actions')}:{labels[sid]['label']}" for sid in train_ids],
                          args.folds, config["split"]["seed"])
    table = threshold_table(answers, y, config["categories"], THRESHOLDS)
    chosen = choose(table, args.min_precision)

    out_dir = RESULTS / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-tune-tfidf")
    out_dir.mkdir(parents=True)
    table.to_csv(out_dir / "thresholds.csv", index=False)

    print(f"Train samples: {len(train_ids)}; {args.folds}-fold grouped CV; excerpt profile: {excerpt_profile()}")
    print(table.round(3).to_string(index=False))
    rule = f"lowest threshold with accuracy when answered >= {args.min_precision}" if args.min_precision is not None \
        else "highest accuracy (unknown counts as wrong)"
    current = config["tfidf"]["abstain_below"]
    if chosen is None:
        print(f"\nNo threshold meets the target ({rule}).")
    else:
        print(f"\nChosen by {rule}: abstain_below = {chosen}  (config.toml currently {current})")
    print(f"Table: {out_dir / 'thresholds.csv'}")


if __name__ == "__main__":
    main()
