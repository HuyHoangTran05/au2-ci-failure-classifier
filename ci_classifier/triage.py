"""Measure human triage time with and without the classifier's hint.

Each sample is shown under one of two conditions, balanced and in random order:
  A  log only
  B  log + predicted category, evidence line and runbook
The participant picks the cause. Time to answer and correctness go to data/triage_sessions.jsonl,
and `python -m ci_classifier evaluate` summarises them.

Use test-set samples and, ideally, a participant who did not label them (a labeller remembers answers).

Usage:
    python -m ci_classifier triage --participant an --count 20
"""

from __future__ import annotations

import argparse
import random
import time
import uuid

from .common import (TRIAGE_LOG, UNKNOWN, append_jsonl, load_config, now_iso, read_excerpt, read_jsonl, read_labels,
                     read_split, runbook_for)
from .methods import METHODS, build_predictor

CLEAR = "\033[2J\033[H"


def ask_category(categories: list[str]) -> str | None:
    menu = "   ".join(f"[{i}] {name}" for i, name in enumerate(categories, start=1))
    while True:
        answer = input(f"\n{menu}   [q] thoát > ").strip().lower()
        if answer == "q":
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(categories):
            return categories[int(answer) - 1]
        print("Không hợp lệ, nhập lại.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier triage", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--participant", required=True, help="short name of the person triaging")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--method", choices=METHODS, default="rules", help="classifier used for hints")
    args = parser.parse_args(argv)

    config = load_config()
    categories = config["categories"]
    labels = read_labels()
    split = read_split()
    if split is None:
        parser.error("no data/split.json yet; run `python -m ci_classifier split` first")
    try:
        predict = build_predictor(args.method, config, labels, split)
    except ValueError as exc:
        parser.error(str(exc))

    done = {r["sample_id"] for r in read_jsonl(TRIAGE_LOG) if r["participant"] == args.participant}
    candidates = [sid for sid in split["test"] if sid in labels and sid not in done]
    rng = random.Random()
    rng.shuffle(candidates)
    queue = candidates[: args.count]
    conditions = ["A", "B"] * (len(queue) // 2 + 1)
    rng.shuffle(conditions)

    session = uuid.uuid4().hex[:8]
    print(f"Session {session}: {len(queue)} samples for {args.participant}. Press Enter to start.")
    input()
    for index, (sample_id, condition) in enumerate(zip(queue, conditions), start=1):
        excerpt = read_excerpt(sample_id)
        category, detail = predict(excerpt) or (UNKNOWN, "no stored LLM answer; run llm-run first")
        print(CLEAR + excerpt.rstrip())
        print("=" * 100)
        print(f"[{index}/{len(queue)}] Nguyên nhân khiến CI fail là gì?")
        if condition == "B":
            print(f"Gợi ý từ bộ phân loại: {category}   ({detail or 'no evidence'})")
            print(f"Runbook: {runbook_for(category, config) or '-'}")
        started = time.monotonic()
        answer = ask_category(categories)
        if answer is None:
            break
        append_jsonl(TRIAGE_LOG, {
            "session": session, "participant": args.participant, "sample_id": sample_id,
            "condition": condition, "method": args.method, "predicted": category, "answer": answer,
            "label": labels[sample_id]["label"], "correct": answer == labels[sample_id]["label"],
            "seconds": round(time.monotonic() - started, 1), "at": now_iso(),
        })
    print("Saved to data/triage_sessions.jsonl.")


if __name__ == "__main__":
    main()
