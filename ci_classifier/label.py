"""Label excerpts by hand in the terminal. Every answer is saved immediately.

Usage:
    python -m ci_classifier label
    python -m ci_classifier label --source logchunks       # fast: shows the human-marked failure chunk
    python -m ci_classifier label --relabel dotnet__aspire__34815567672
    python -m ci_classifier label --review                 # check draft labels written by Claude
    python -m ci_classifier label --accept-drafts <name>   # drafts were checked elsewhere; keep them as human labels
    python -m ci_classifier label --blind --labeler <name> --count 80   # relabel test samples without seeing labels
    python -m ci_classifier label --adjudicate --labeler <name>         # settle blind vs draft disagreements

For LogChunks samples, a label is also applied to unlabelled samples with an identical chunk
(recorded in the note); pass --no-propagate to label each one yourself.

Predictions are deliberately not shown, so the labels stay independent of the classifiers.
Blind labels go to data/blind_labels.jsonl and never change data/labels.jsonl; `python -m ci_classifier agreement`
compares them with the drafts. Only --adjudicate writes a final label back to labels.jsonl.
"""

from __future__ import annotations

import argparse
import random
import time
import webbrowser

from . import agreement
from .common import (DRAFT_LABELER, append_label, excerpt_path, load_config, read_excerpt, read_labels, read_manifest,
                     read_split)

GITHUB_ACTIONS = "github-actions"


def source_of(record: dict) -> str:
    return record.get("source", GITHUB_ACTIONS)


def chunk_key(record: dict) -> str:
    return " ".join(record.get("chunk", "").split())


def show(sample_id: str, record: dict, position: str, full_excerpt: bool) -> None:
    print("\n" + "=" * 100)
    if full_excerpt or not record.get("chunk"):
        print(read_excerpt(sample_id).rstrip())
        print("=" * 100)
    print(f"{position}  {sample_id}")
    print(f"repo: {record['repo']}   workflow: {record['workflow']}   source: {source_of(record)}")
    print(f"title: {record['title']}")
    if record.get("chunk"):
        print("\n-- Đoạn log con người đã đánh dấu là nguyên nhân (LogChunks) --")
        print(record["chunk"].rstrip())
        print("-" * 100)


def ask(sample_id: str, record: dict, categories: list[str], position: str,
        draft: dict | None = None) -> tuple[str, str] | None:
    """Return (label, note), ("", "") to skip, or None to quit. With a draft, Enter keeps the draft label."""
    show(sample_id, record, position, full_excerpt=False)
    if draft:
        print(f"Nhãn nháp: {draft['label']}   ({draft.get('note', '')})")
    menu = "   ".join(f"[{i}] {name}" for i, name in enumerate(categories, start=1))
    extra = "[e] xem đoạn log đầy đủ   " if record.get("chunk") else ""
    keep = "[Enter] giữ nhãn nháp   " if draft else ""
    while True:
        answer = input(f"{menu}\n{keep}{extra}[o] mở URL   [s] bỏ qua   [q] thoát > ").strip().lower()
        if draft and answer == "":
            return draft["label"], "reviewed: kept draft"
        if answer == "q":
            return None
        if answer == "s":
            return "", ""
        if answer == "o":
            webbrowser.open(record["url"])
            continue
        if answer == "e" and extra:
            show(sample_id, record, position, full_excerpt=True)
            continue
        if answer.isdigit() and 1 <= int(answer) <= len(categories):
            chosen = categories[int(answer) - 1]
            note = input("Ghi chú (Enter để bỏ qua) > ").strip()
            if draft:
                verdict = "kept draft" if chosen == draft["label"] else f"changed from {draft['label']}"
                note = f"reviewed: {verdict}" + (f"; {note}" if note else "")
            return chosen, note
        print("Không hợp lệ, nhập lại.")


def run_blind(queue: list[str], manifest: dict[str, dict], categories: list[str], labeler: str) -> int:
    """Ask for each sample without showing any existing label; skips are stored as unclear (label null)."""
    done = 0
    for index, sample_id in enumerate(queue, start=1):
        started = time.monotonic()
        result = ask(sample_id, manifest[sample_id], categories, f"[mù {index}/{len(queue)}]")
        if result is None:
            break
        label, note = result
        agreement.append_blind(sample_id, label or None, labeler, time.monotonic() - started,
                               note if label else "skipped: unclear")
        done += 1
    return done


def adjudication_choice(sample_id: str, candidates: tuple[str, str], categories: list[str]) -> str | None:
    """Show two candidate labels in a per-sample random order, without saying which is the draft."""
    first, second = sorted(candidates)
    if random.Random(sample_id).random() < 0.5:
        first, second = second, first
    print(f"Hai nhãn đang bất đồng (thứ tự ngẫu nhiên, không cho biết nhãn nào của ai): {first}  |  {second}")
    menu = "   ".join(f"[{i}] {name}" for i, name in enumerate(categories, start=1))
    while True:
        answer = input(f"{menu}\n[s] bỏ qua   [q] thoát > ").strip().lower()
        if answer == "q":
            return None
        if answer == "s":
            return ""
        if answer.isdigit() and 1 <= int(answer) <= len(categories):
            return categories[int(answer) - 1]
        print("Không hợp lệ, nhập lại.")


def run_adjudication(queue: list[str], manifest: dict[str, dict], categories: list[str], labeler: str,
                     drafts: dict[str, str], blind: dict[str, dict]) -> int:
    settled = 0
    for index, sample_id in enumerate(queue, start=1):
        record = manifest[sample_id]
        show(sample_id, record, f"[phân xử {index}/{len(queue)}]", full_excerpt=True)
        draft, relabel = drafts[sample_id], blind[sample_id]["label"]
        chosen = adjudication_choice(sample_id, (draft, relabel), categories)
        if chosen is None:
            break
        if not chosen:
            continue
        append_label(sample_id, chosen, f"{agreement.ADJUDICATED} by {labeler}: draft={draft}, blind={relabel}")
        settled += 1
    return settled


def accept_drafts(labels: dict[str, dict], wanted, reviewer: str) -> int:
    """Append a human record keeping each draft label; the note keeps it distinct from one-by-one review."""
    accepted = 0
    for sid, record in labels.items():
        if record.get("labeler") == DRAFT_LABELER and wanted(sid):
            append_label(sid, record["label"], f"reviewed: bulk accepted by {reviewer} (draft kept); "
                                               f"draft note: {record.get('note', '')}")
            accepted += 1
    return accepted


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier label", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--relabel", metavar="SAMPLE_ID", help="label one sample again")
    parser.add_argument("--source", choices=[GITHUB_ACTIONS, "logchunks"], help="only label samples from this source")
    parser.add_argument("--no-propagate", action="store_true", help="do not copy labels to identical chunks")
    parser.add_argument("--review", action="store_true",
                        help=f"review draft labels ({DRAFT_LABELER}): Enter keeps, a number changes")
    parser.add_argument("--accept-drafts", metavar="REVIEWER",
                        help="record that REVIEWER checked the draft labels outside this tool and keeps them all")
    parser.add_argument("--blind", action="store_true",
                        help="relabel test samples without seeing their labels (stored in data/blind_labels.jsonl)")
    parser.add_argument("--adjudicate", action="store_true",
                        help="choose the final label where a blind label disagrees with the draft")
    parser.add_argument("--labeler", help="your name (required with --blind and --adjudicate)")
    parser.add_argument("--count", type=int, default=80, help="size of the blind sample (default 80)")
    args = parser.parse_args(argv)
    if (args.blind or args.adjudicate) and not args.labeler:
        parser.error("--blind and --adjudicate need --labeler <name>")

    config = load_config()
    categories = config["categories"]
    manifest = read_manifest()
    labels = read_labels()

    def wanted(sid: str) -> bool:
        return sid in manifest and (args.source is None or source_of(manifest[sid]) == args.source)

    if args.accept_drafts:
        accepted = accept_drafts(labels, wanted, args.accept_drafts)
        print(f"Recorded {accepted} draft labels as accepted by {args.accept_drafts}.")
        return

    if args.blind:
        split = read_split()
        if split is None:
            parser.error("no data/split.json yet; run `python -m ci_classifier split` first")
        test_ids = [sid for sid in split["test"] if sid in labels and wanted(sid)]
        done = set(agreement.read_blind(args.labeler))
        queue = agreement.blind_queue(test_ids, manifest, done, args.count, config["split"]["seed"])
        print(f"Blind relabel: {len(queue)} of {args.count} samples left for {args.labeler}. Existing labels, notes and "
              "predictions are hidden. Guide: docs/labeling-guide.md. [s] = unclear, [q] = stop (resume later).")
        stored = run_blind(queue, manifest, categories, args.labeler)
        print(f"Saved {stored} blind labels. Compare: python -m ci_classifier agreement --labeler {args.labeler}")
        return

    if args.adjudicate:
        drafts, blind = agreement.original_drafts(), agreement.read_blind(args.labeler)
        queue = [sid for sid in agreement.adjudication_queue(blind, drafts, labels) if wanted(sid)]
        print(f"{len(queue)} disagreements to settle. The chosen label becomes the label used by evaluate.")
        settled = run_adjudication(queue, manifest, categories, args.labeler, drafts, blind)
        print(f"Settled {settled}. Re-run `python -m ci_classifier evaluate --cv 5` to score against the new labels.")
        return

    if args.relabel:
        queue = [args.relabel]
    elif args.review:
        queue = [sid for sid, label in labels.items() if label.get("labeler") == DRAFT_LABELER and wanted(sid)]
    else:
        queue = [sid for sid in manifest if excerpt_path(sid).exists() and sid not in labels and wanted(sid)]
    if not args.relabel:
        # Shuffle with a fixed seed so consecutive samples do not all come from one repo.
        random.Random(config["split"]["seed"]).shuffle(queue)

    todo = "drafts to review" if args.review else "to go"
    print(f"{len(labels)} samples labelled, {len(queue)} {todo}. Guide: docs/labeling-guide.md")
    done_now: set[str] = set()
    for index, sample_id in enumerate(queue, start=1):
        if sample_id in done_now:
            continue
        record = manifest[sample_id]
        draft = labels[sample_id] if args.review else None
        result = ask(sample_id, record, categories, f"[{index}/{len(queue)}]", draft)
        if result is None:
            break
        label, note = result
        if not label:
            continue
        append_label(sample_id, label, note)
        done_now.add(sample_id)

        key = chunk_key(record)
        if key and not args.no_propagate and not args.relabel:
            # In review mode the queue holds only drafts, so twins are drafts with the identical chunk.
            twins = [sid for sid in queue if sid not in done_now and chunk_key(manifest[sid]) == key]
            for twin in twins:
                append_label(twin, label, f"auto: same chunk as {sample_id}" + (f"; {note}" if note else ""))
                done_now.add(twin)
            if twins:
                print(f"Also labelled {len(twins)} samples with the identical chunk as {label}.")
    print(f"Saved. Total labelled: {len(read_labels())}.")


if __name__ == "__main__":
    main()
