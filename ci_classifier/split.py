"""Split labelled samples into train and test sets, once.

Samples from the same (repo, workflow) always land on the same side: runs of one workflow often
have near-identical logs, and letting them straddle the split would inflate test scores.

Usage:
    python -m ci_classifier split           # create data/split.json
    python -m ci_classifier split --extend  # add newly labelled samples, keeping existing assignments
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict

from .common import SPLIT, load_config, now_iso, read_labels, read_manifest, read_split


def group_of(record: dict) -> str:
    return f"{record['repo']}::{record['workflow']}"


def make_split(sample_ids: list[str], manifest: dict[str, dict], test_fraction: float, seed: int) -> dict:
    groups: dict[str, list[str]] = defaultdict(list)
    for sample_id in sorted(sample_ids):
        groups[group_of(manifest[sample_id])].append(sample_id)
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)

    target = round(len(sample_ids) * test_fraction)
    train: list[str] = []
    test: list[str] = []
    for key in keys:
        (test if len(test) < target else train).extend(groups[key])
    return {"seed": seed, "test_fraction": test_fraction, "created_at": now_iso(), "train": train, "test": test}


def extend_split(split: dict, sample_ids: list[str], manifest: dict[str, dict]) -> int:
    side_of_group = {}
    for side in ("train", "test"):
        for sample_id in split[side]:
            side_of_group[group_of(manifest[sample_id])] = side
    assigned = set(split["train"]) | set(split["test"])
    added = 0
    for sample_id in sorted(set(sample_ids) - assigned):
        group = group_of(manifest[sample_id])
        if group not in side_of_group:
            # Deterministic for unseen groups, independent of labelling order.
            bucket = int(hashlib.sha256(f"{split['seed']}:{group}".encode()).hexdigest(), 16) % 1000
            side_of_group[group] = "test" if bucket < split["test_fraction"] * 1000 else "train"
        split[side_of_group[group]].append(sample_id)
        added += 1
    return added


def describe(split: dict, labels: dict[str, dict]) -> None:
    for side in ("train", "test"):
        counts = Counter(labels[sid]["label"] for sid in split[side] if sid in labels)
        print(f"{side}: {len(split[side])} samples  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier split", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extend", action="store_true", help="assign newly labelled samples to the existing split")
    parser.add_argument("--force", action="store_true", help="discard the existing split and create a new one")
    args = parser.parse_args(argv)

    cfg = load_config()["split"]
    manifest = read_manifest()
    labels = read_labels()
    existing = read_split()

    if existing and args.extend:
        added = extend_split(existing, list(labels), manifest)
        split = existing
        print(f"Added {added} samples to the existing split.")
    elif existing and not args.force:
        print("data/split.json already exists. Use --extend for new labels, or --force to start over")
        print("(--force invalidates any tuning you did while looking at the old train set).")
        describe(existing, labels)
        return
    else:
        split = make_split(list(labels), manifest, cfg["test_fraction"], cfg["seed"])

    SPLIT.write_text(json.dumps(split, indent=2), encoding="utf-8")
    describe(split, labels)


if __name__ == "__main__":
    main()
