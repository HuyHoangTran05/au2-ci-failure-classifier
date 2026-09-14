"""Baseline 1: keyword rules.

Categories are checked in priority order and the first match wins, so a dependency error that
also produces "Build FAILED" is reported as dependency. No match returns "unknown".

Usage (for tuning - look only at the train set, never at test):
    python -m ci_classifier rules --split train
"""

from __future__ import annotations

import argparse
import re
from collections import Counter

from .common import UNKNOWN, excerpt_path, read_excerpt, read_labels, read_manifest, read_split

RULES: list[tuple[str, list[str]]] = [
    ("infrastructure", [
        r"No space left on device",
        r"The runner has received a shutdown signal",
        r"lost communication with the server",
        r"The operation was canceled",
        r"has exceeded the maximum execution time",
        r"Could not resolve host",
        r"Connection reset by peer",
        r"\b50[23] (?:Bad Gateway|Service Unavailable)",
        r"\b(?:ETIMEDOUT|ECONNRESET|ECONNREFUSED)\b",
        r"OOMKilled|out of memory|Killed.*signal 9",
    ]),
    ("authentication", [
        r"Unauthori[sz]ed|HTTP 401|status code 401",
        r"403 Forbidden|HTTP 403",
        r"Bad credentials",
        r"[Aa]uthentication (?:failed|required)",
        r"Resource not accessible by integration",
        r"Permission denied \(publickey\)",
        r"Input required and not supplied",
        r"AADSTS\d+",
        r"denied: requested access",
    ]),
    ("dependency", [
        r"npm ERR!|npm error",
        r"\bERESOLVE\b",
        r"No matching distribution found|ResolutionImpossible|Could not find a version that satisfies",
        r"Unable to find package|\bNU1(?:101|102|605)\b",
        r"ModuleNotFoundError|No module named",
        r"Cannot find module",
        r"E: Unable to locate package",
        r"Could not resolve dependencies",
    ]),
    ("compilation", [
        r"error CS\d{4}",
        r"error TS\d{4}",
        r"error\[E\d{4}\]",
        r"^\S+:\d+(?::\d+)?: (?:fatal )?error:",
        r"undefined reference to",
        r"cannot find symbol",
        r"\bSyntaxError\b",
        r"Build FAILED",
    ]),
    ("other", [
        r"would reformat|Code style issues|Formatting check failed",
        r"\beslint\b.*\berrors?\b|\d+ problems? \(\d+ errors?",
        r"\bruff\b.*\berror|\bflake8\b|\bmypy\b.*error",
        r"[Mm]issing (?:required )?label",
    ]),
    ("test_assertion", [
        r"AssertionError",
        r"Assert\.\w+\(\) Failure",
        r"--- FAIL:",
        r"\b\d+ failing\b|Snapshot .* does not match",
        r"\b\d+ (?:tests? )?failed\b|\btests? failed\b",
        r"\bFAILED\b",
        r"expect\(.*\)\.(?:to|not)",
        r"Result: FAILURE",
    ]),
]

COMPILED = [(category, [re.compile(p, re.MULTILINE) for p in patterns]) for category, patterns in RULES]


def classify(text: str) -> tuple[str, str]:
    """Return (category, evidence line) for one excerpt."""
    for category, patterns in COMPILED:
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                start = text.rfind("\n", 0, match.start()) + 1
                end = text.find("\n", match.end())
                return category, text[start : end if end != -1 else None].strip()
    return UNKNOWN, ""


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier rules", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["train", "all"], default="train",
                        help="train: labelled train samples; all: every excerpt, labelled or not")
    args = parser.parse_args(argv)

    labels = read_labels()
    if args.split == "train":
        split = read_split()
        if split is None:
            parser.error("no data/split.json yet; run `python -m ci_classifier split` or use --split all")
        sample_ids = [sid for sid in split["train"] if sid in labels]
    else:
        sample_ids = [sid for sid in read_manifest() if excerpt_path(sid).exists()]

    predicted: Counter[str] = Counter()
    correct = 0
    for sample_id in sample_ids:
        category, evidence = classify(read_excerpt(sample_id))
        predicted[category] += 1
        truth = labels.get(sample_id, {}).get("label")
        if truth == category:
            correct += 1
        elif truth or args.split == "all":
            shown = f"label={truth} " if truth else ""
            print(f"{sample_id}: {shown}predicted={category}  | {evidence[:150]}")

    print(f"\n{len(sample_ids)} samples; predictions: " + ", ".join(f"{k}={v}" for k, v in predicted.most_common()))
    labelled = sum(1 for sid in sample_ids if sid in labels)
    if labelled:
        print(f"Correct on labelled samples: {correct}/{labelled}")


if __name__ == "__main__":
    main()
