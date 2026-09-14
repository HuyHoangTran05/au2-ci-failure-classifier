"""Label excerpts by hand in the terminal. Every answer is saved immediately.

Usage:
    python -m ci_classifier label
    python -m ci_classifier label --relabel dotnet__aspire__34815567672

Predictions are deliberately not shown, so the labels stay independent of the classifiers.
"""

from __future__ import annotations

import argparse
import random
import webbrowser

from .common import append_label, excerpt_path, load_config, read_excerpt, read_labels, read_manifest


def ask(sample_id: str, record: dict, categories: list[str], position: str) -> tuple[str, str] | None:
    """Return (label, note), ("", "") to skip, or None to quit."""
    print("\n" + "=" * 100)
    print(read_excerpt(sample_id).rstrip())
    print("=" * 100)
    print(f"{position}  {sample_id}")
    print(f"repo: {record['repo']}   workflow: {record['workflow']}   event: {record['event']}")
    print(f"title: {record['title']}")
    print(f"url: {record['url']}")
    menu = "   ".join(f"[{i}] {name}" for i, name in enumerate(categories, start=1))
    while True:
        answer = input(f"{menu}\n[o] mở URL   [s] bỏ qua   [q] thoát > ").strip().lower()
        if answer == "q":
            return None
        if answer == "s":
            return "", ""
        if answer == "o":
            webbrowser.open(record["url"])
            continue
        if answer.isdigit() and 1 <= int(answer) <= len(categories):
            note = input("Ghi chú (Enter để bỏ qua) > ").strip()
            return categories[int(answer) - 1], note
        print("Không hợp lệ, nhập lại.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier label", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--relabel", metavar="SAMPLE_ID", help="label one sample again")
    args = parser.parse_args(argv)

    config = load_config()
    categories = config["categories"]
    manifest = read_manifest()
    labels = read_labels()

    if args.relabel:
        queue = [args.relabel]
    else:
        queue = [sid for sid in manifest if excerpt_path(sid).exists() and sid not in labels]
        # Shuffle with a fixed seed so consecutive samples do not all come from one repo.
        random.Random(config["split"]["seed"]).shuffle(queue)

    print(f"{len(labels)} samples labelled, {len(queue)} to go. Guide: docs/labeling-guide.md")
    for index, sample_id in enumerate(queue, start=1):
        result = ask(sample_id, manifest[sample_id], categories, f"[{index}/{len(queue)}]")
        if result is None:
            break
        label, note = result
        if label:
            append_label(sample_id, label, note)
    print(f"Saved. Total labelled: {len(read_labels())}.")


if __name__ == "__main__":
    main()
