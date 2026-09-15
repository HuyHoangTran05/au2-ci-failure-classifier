"""Agreement between blind relabels and the original draft labels, and whether drafts inflate classifier scores.

`label --blind` stores independent labels in data/blind_labels.jsonl without showing the existing label. This
command compares them with the first draft label of each sample (written by Claude) and reports:
  - raw agreement and Cohen's kappa, with 95% cluster-bootstrap intervals over (repo, workflow) groups
  - a draft x blind confusion matrix and the list of disagreements (adjudicate them with `label --adjudicate`)
  - each classifier's accuracy against the draft labels and against the blind labels on the same samples;
    a method that agrees clearly more with the drafts than with the blind labels was helped by the drafts

Usage:
    python -m ci_classifier agreement
    python -m ci_classifier agreement --labeler HuyHoangTran
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from . import stats
from .common import (BLIND_LABELS, DRAFT_LABELER, LABELS, RESULTS, append_jsonl, load_config, now_iso, read_excerpt,
                     read_jsonl, read_labels, read_manifest, read_split)
from .methods import METHODS, build_predictor
from .split import group_of

BLIND_PROTOCOL = "blind-v1"


def chunk_key(record: dict) -> str:
    return " ".join(record.get("chunk", "").split())


def read_blind(labeler: str | None = None) -> dict[str, dict]:
    """Latest blind record per sample (for one labeler, or the latest from anyone)."""
    return {r["sample_id"]: r for r in read_jsonl(BLIND_LABELS) if labeler is None or r["labeler"] == labeler}


def original_drafts() -> dict[str, str]:
    """The first draft label of each sample, before any review or adjudication changed it."""
    drafts: dict[str, str] = {}
    for record in read_jsonl(LABELS):
        if record.get("labeler") == DRAFT_LABELER:
            drafts.setdefault(record["sample_id"], record["label"])
    return drafts


def append_blind(sample_id: str, label: str | None, labeler: str, seconds: float, note: str = "") -> None:
    append_jsonl(BLIND_LABELS, {"sample_id": sample_id, "label": label, "labeler": labeler, "note": note,
                                "seconds": round(seconds, 1), "protocol": BLIND_PROTOCOL, "at": now_iso()})


def blind_queue(test_ids: list[str], manifest: dict[str, dict], done: set[str], count: int, seed: int) -> list[str]:
    """The first `count` test samples in a fixed random order, one per identical LogChunks chunk, minus those done.

    The order depends only on the seed and the test set, so a session can stop and resume on the same sample list.
    """
    order = sorted(test_ids)
    random.Random(f"{seed}:blind").shuffle(order)
    chosen: list[str] = []
    chunks: set[str] = set()
    for sid in order:
        key = chunk_key(manifest[sid])
        if key:
            if key in chunks:
                continue
            chunks.add(key)
        chosen.append(sid)
        if len(chosen) == count:
            break
    return [sid for sid in chosen if sid not in done]


ADJUDICATED = "adjudicated"


def adjudication_queue(blind: dict[str, dict], drafts: dict[str, str], labels: dict[str, dict]) -> list[str]:
    """Samples whose blind label differs from the draft and whose current label was not adjudicated yet."""
    return sorted(sid for sid, record in blind.items()
                  if record.get("label") and sid in drafts and record["label"] != drafts[sid]
                  and not labels[sid].get("note", "").startswith(ADJUDICATED))


def kappa(y_a: np.ndarray, y_b: np.ndarray, categories) -> float:
    if len(y_a) == 0:
        return math.nan
    if len(set(y_a) | set(y_b)) == 1:
        return 1.0  # both raters used one identical category everywhere: perfect, but kappa is undefined
    return float(cohen_kappa_score(y_a, y_b, labels=list(categories)))


def compare(draft: list[str], blind: list[str], groups: list[str], categories: list[str],
            samples: int, seed: int) -> dict:
    result = {"n": len(draft)}
    for name, metric in (("agreement", stats.accuracy), ("kappa", kappa)):
        point, low, high = stats.group_bootstrap_ci(draft, blind, groups, metric, categories, samples, seed)
        result.update({name: point, f"{name}_low": low, f"{name}_high": high})
    return result


def method_bias(predictions: dict[str, list[str]], draft: list[str], blind: list[str]) -> pd.DataFrame:
    """Accuracy of each method against draft and blind labels on the same samples, with a McNemar test."""
    rows = []
    draft_arr, blind_arr = np.array(draft), np.array(blind)
    for method, predicted in predictions.items():
        pred = np.array(predicted)
        vs_draft, vs_blind = pred == draft_arr, pred == blind_arr
        test = stats.mcnemar_exact(vs_draft, vs_blind)
        rows.append({"method": method, "samples": len(pred), "accuracy_vs_draft": vs_draft.mean(),
                     "accuracy_vs_blind": vs_blind.mean(), "only_draft_match": test["a_only"],
                     "only_blind_match": test["b_only"], "p_value": test["p_value"]})
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier agreement", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--labeler", help="only blind labels by this person (default: everyone's latest)")
    args = parser.parse_args(argv)

    config = load_config()
    categories = config["categories"]
    manifest, labels, split = read_manifest(), read_labels(), read_split()
    drafts = original_drafts()
    blind_all = read_blind(args.labeler)
    skipped = sorted(sid for sid, r in blind_all.items() if not r.get("label"))
    blind = {sid: r for sid, r in blind_all.items() if r.get("label") and sid in drafts}
    if not blind:
        raise SystemExit("No blind labels yet. Run `python -m ci_classifier label --blind --labeler <name>` first.")

    ids = sorted(blind)
    draft_y = [drafts[sid] for sid in ids]
    blind_y = [blind[sid]["label"] for sid in ids]
    groups = [group_of(manifest[sid]) for sid in ids]
    eval_cfg = config["evaluation"]
    overall = compare(draft_y, blind_y, groups, categories, eval_cfg["bootstrap_samples"], config["split"]["seed"])

    by_source = []
    for source in sorted({manifest[sid].get("source", "github-actions") for sid in ids}):
        idx = [i for i, sid in enumerate(ids) if manifest[sid].get("source", "github-actions") == source]
        pick = lambda values: [values[i] for i in idx]
        by_source.append({"source": source, **compare(pick(draft_y), pick(blind_y), pick(groups), categories,
                                                      eval_cfg["bootstrap_samples"], config["split"]["seed"])})

    confusion = (pd.crosstab(pd.Series(draft_y, name="draft"), pd.Series(blind_y, name="blind"))
                 .reindex(index=categories, columns=categories, fill_value=0))

    texts = [read_excerpt(sid) for sid in ids]
    predictions = {}
    for method in METHODS:
        try:
            predict = build_predictor(method, config, labels, split)
        except ValueError as exc:
            print(f"{method} skipped: {exc}")
            continue
        answers = [predict(text) for text in texts]
        if all(answer is not None for answer in answers):
            predictions[method] = [answer[0] for answer in answers]
        else:
            print(f"{method} skipped: {sum(a is None for a in answers)} samples have no stored LLM answer")
    bias = method_bias(predictions, draft_y, blind_y)

    disagreements = pd.DataFrame([
        {"sample_id": sid, "source": manifest[sid].get("source", "github-actions"), "draft": drafts[sid],
         "blind": blind[sid]["label"], "current": labels[sid]["label"], "blind_note": blind[sid].get("note", "")}
        for sid in ids if drafts[sid] != blind[sid]["label"]])
    seconds = [r["seconds"] for r in blind.values() if r.get("seconds") is not None]
    test_set = set(split["test"]) if split else set()
    in_test = sum(sid in test_set for sid in ids)

    out_dir = RESULTS / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-agreement")
    out_dir.mkdir(parents=True)
    disagreements.to_csv(out_dir / "disagreements.csv", index=False)
    summary = {
        "created_at": now_iso(), "labeler": args.labeler or "all", "protocol": BLIND_PROTOCOL,
        "blind_labelled": len(ids), "blind_skipped": len(skipped), "in_test_set": in_test,
        "median_seconds_per_sample": float(np.median(seconds)) if seconds else None,
        "overall": overall, "by_source": by_source,
        "confusion_draft_rows_blind_columns": confusion.to_dict("index"),
        "method_bias": bias.to_dict("records"),
    }
    (out_dir / "agreement.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")

    print(f"Blind labels: {len(ids)} compared ({in_test} in the test set), {len(skipped)} skipped as unclear; "
          f"median {summary['median_seconds_per_sample']} s per sample")
    print(f"Agreement with drafts: {overall['agreement']:.2f} [{overall['agreement_low']:.2f}, "
          f"{overall['agreement_high']:.2f}]   Cohen's kappa: {overall['kappa']:.2f} "
          f"[{overall['kappa_low']:.2f}, {overall['kappa_high']:.2f}]")
    for row in by_source:
        print(f"  {row['source']:15} n={row['n']:3}  agreement={row['agreement']:.2f}  kappa={row['kappa']:.2f}")
    print("\nDraft (rows) x blind (columns):")
    print(confusion.to_string())
    print("\nClassifier accuracy against draft vs blind labels (same samples):")
    print(bias.round(3).to_string(index=False))
    print(f"\nDisagreements: {len(disagreements)} -> {out_dir / 'disagreements.csv'}")
    if len(disagreements):
        print("Settle them with `python -m ci_classifier label --adjudicate --labeler <name>`.")
    print(f"Summary: {out_dir / 'agreement.json'}")
    if len(ids) < 30:
        print(f"Note: only {len(ids)} blind labels; intervals are wide. Aim for 60-80.")


if __name__ == "__main__":
    main()
