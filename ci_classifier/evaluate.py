"""Compare the classifiers on the held-out test set and write a report.

Usage:
    python -m ci_classifier evaluate

Output: results/<timestamp>/report.md (Jinja2), metrics.json, predictions.csv
Triage-time sessions from `python -m ci_classifier triage` are summarised when present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from .common import (DRAFT_LABELER, LABELS, RESULTS, TRIAGE_LOG, UNKNOWN, load_config, now_iso, read_excerpt, read_jsonl,
                     read_labels, read_manifest, read_split)
from .methods import METHODS, build_predictor

SMALL_TEST_SET = 30
TITLES = {"rules": "Baseline 1 - keyword rules", "tfidf": "Baseline 2 - TF-IDF + logistic regression"}
CONDITIONS = {"A": "A - log only", "B": "B - log + classifier hint"}


def compute_metrics(y_true: list[str], y_pred: list[str], categories: list[str]) -> dict:
    """Per-category precision/recall/F1 plus abstention; "unknown" predictions count as wrong."""
    df = pd.DataFrame({"label": y_true, "pred": y_pred})
    correct = df["label"] == df["pred"]
    answered = df["pred"] != UNKNOWN

    support = df["label"].value_counts().reindex(categories, fill_value=0)
    predicted = df["pred"].value_counts().reindex(categories, fill_value=0)
    true_pos = df.loc[correct, "label"].value_counts().reindex(categories, fill_value=0)
    precision = (true_pos / predicted).where(predicted > 0)
    recall = (true_pos / support).where(support > 0)
    f1 = 2 * precision * recall / (precision + recall)
    # A category that occurs but is never predicted correctly scores 0, not "undefined".
    f1 = f1.mask((support > 0) & f1.isna(), 0.0)

    per_category = pd.DataFrame({"precision": precision, "recall": recall, "f1": f1,
                                 "support": support, "predicted": predicted})
    per_category.index.name = "category"
    confusion = (pd.crosstab(df["label"], df["pred"])
                 .reindex(index=categories, columns=[*categories, UNKNOWN], fill_value=0))

    summary = {
        "n": len(df),
        "accuracy": correct.mean(),
        "abstention_rate": 1 - answered.mean(),
        "accuracy_when_answered": correct[answered].mean() if answered.any() else math.nan,
        "macro_f1": per_category["f1"].mean(),
    }
    return {"summary": summary, "per_category": per_category, "confusion": confusion}


def by_source(predictions: pd.DataFrame, method: str) -> pd.DataFrame:
    """Accuracy and abstention per data source, since Travis CI and GitHub Actions logs differ."""
    return (predictions
            .assign(correct=predictions[method] == predictions["label"], abstained=predictions[method] == UNKNOWN)
            .groupby("source")
            .agg(samples=("label", "size"), accuracy=("correct", "mean"), abstention_rate=("abstained", "mean")))


def triage_summary(records: list[dict]) -> pd.DataFrame | None:
    if not records:
        return None
    df = pd.DataFrame(records)
    table = df.groupby("condition").agg(
        samples=("sample_id", "size"),
        participants=("participant", "nunique"),
        median_seconds=("seconds", "median"),
        mean_seconds=("seconds", "mean"),
        accuracy=("correct", "mean"),
    )
    table.index = table.index.map(lambda c: CONDITIONS.get(c, c))
    return table


def fmt(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def to_json(value):
    """Make metrics JSON-safe: DataFrames become records, NaN becomes null."""
    if isinstance(value, pd.DataFrame):
        return to_json(value.reset_index().to_dict("records"))
    if isinstance(value, dict):
        return {str(k): to_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_json(v) for v in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):  # numpy scalar
        return to_json(value.item())
    return value


def render_report(context: dict) -> str:
    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    env.filters["fmt"] = fmt
    return env.get_template("report.md.j2").render(context)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier evaluate", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)

    config = load_config()
    categories = config["categories"]
    labels = read_labels()
    split = read_split()
    if split is None:
        raise SystemExit("No data/split.json yet. Label samples, then run `python -m ci_classifier split`.")

    unassigned = set(labels) - set(split["train"]) - set(split["test"])
    if unassigned:
        print(f"Warning: {len(unassigned)} labelled samples are not in the split "
              "(run `python -m ci_classifier split --extend`).")

    train_ids = [sid for sid in split["train"] if sid in labels]
    test_ids = [sid for sid in split["test"] if sid in labels]
    if not test_ids:
        raise SystemExit("The test set has no labelled samples.")

    manifest = read_manifest()
    predictions = pd.DataFrame({
        "sample_id": test_ids,
        "source": [manifest[sid].get("source", "github-actions") for sid in test_ids],
        "label": [labels[sid]["label"] for sid in test_ids],
    })
    texts = [read_excerpt(sid) for sid in test_ids]
    results = {}
    for method in METHODS:
        try:
            predict = build_predictor(method, config, labels, split)
        except ValueError as exc:
            print(f"{method} skipped: {exc}")
            continue
        start = time.perf_counter()
        outputs = [predict(text) for text in texts]
        elapsed_ms = (time.perf_counter() - start) * 1000
        predictions[method] = [category for category, _ in outputs]
        predictions[f"{method}_detail"] = [detail[:160] for _, detail in outputs]
        results[method] = compute_metrics(predictions["label"].tolist(), predictions[method].tolist(), categories)
        results[method]["summary"]["ms_per_sample"] = elapsed_ms / len(texts)
        results[method]["by_source"] = by_source(predictions, method)

    run = {
        "created_at": now_iso(),
        "train_samples": len(train_ids),
        "test_samples": len(test_ids),
        "test_label_counts": predictions["label"].value_counts().sort_index().to_dict(),
        "draft_labels_in_test": sum(labels[sid].get("labeler") == DRAFT_LABELER for sid in test_ids),
        "labels_sha256": hashlib.sha256(LABELS.read_bytes()).hexdigest()[:16],
        "split_created_at": split["created_at"],
    }
    triage = triage_summary(read_jsonl(TRIAGE_LOG))

    out_dir = RESULTS / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    predictions.to_csv(out_dir / "predictions.csv", index=False)
    metrics = {"run": run, "config": config, "methods": results, "triage": triage}
    (out_dir / "metrics.json").write_text(json.dumps(to_json(metrics), indent=2), encoding="utf-8")

    method_views = []
    for method, result in results.items():
        mistakes = predictions.loc[predictions[method] != predictions["label"]].head(10)
        method_views.append({
            "title": TITLES[method],
            "summary": result["summary"],
            "per_category": result["per_category"].reset_index().to_dict("records"),
            "by_source": result["by_source"].reset_index().to_dict("records"),
            "confusion_columns": list(result["confusion"].columns),
            "confusion_rows": [(label, row.tolist()) for label, row in result["confusion"].iterrows()],
            "mistakes": [{"sample_id": r["sample_id"], "label": r["label"], "pred": r[method],
                          "detail": r[f"{method}_detail"]} for _, r in mistakes.iterrows()],
        })
    report = render_report({
        "run": run,
        "small_test_set": SMALL_TEST_SET,
        "methods": method_views,
        "triage": None if triage is None else triage.reset_index().to_dict("records"),
    })
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    for method, result in results.items():
        s = result["summary"]
        print(f"{method:6} accuracy={fmt(s['accuracy'])} abstention={fmt(s['abstention_rate'])} "
              f"macro_f1={fmt(s['macro_f1'])}")
    if triage is not None:
        print(triage.to_string())
    print(f"Report: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
