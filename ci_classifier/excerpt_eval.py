"""Measure how well excerpts keep the failure cause, using LogChunks' human-marked chunks as ground truth.

For every LogChunks sample the excerpt is rebuilt from the raw log and compared with the marked chunk:
- full coverage: every chunk line appears in the excerpt
- line coverage: share of chunk lines that appear
- size: excerpt lines and characters (a strategy must not win by simply keeping more text)
Misses get a diagnosed reason. Results are split by train/test so a strategy can be tuned on train only.

Usage:
    python -m ci_classifier excerpt-eval
    python -m ci_classifier excerpt-eval --set context_before_error=120
    python -m ci_classifier excerpt-eval --set strategy=hints --set hint_budget=80
"""

from __future__ import annotations

import argparse
import gzip
from collections import Counter

import pandas as pd

from .common import excerpt_profile, excerpt_settings, load_config, raw_path, read_manifest, read_split
from .excerpt import ERROR_MARKER, build_excerpt, parse_jobs
from .logchunks import normalize_line

REASONS = [
    "covered", "no error marker", "chunk after last marker", "chunk far before marker",
    "chunk longer than window", "line truncated", "trimmed by line budget", "chunk not found in raw log",
]


def diagnose(chunk_lines: list[str], raw_text: str, cfg: dict) -> str:
    """Explain why a chunk is not fully inside the excerpt (heuristic, for error analysis)."""
    lines = [normalize_line(line) for job in parse_jobs(raw_text).values() for line in job]
    first = chunk_lines[0][:60]
    positions = [i for i, line in enumerate(lines) if first in line]
    if not positions:
        return "chunk not found in raw log"
    start = positions[-1]
    end = start + len(chunk_lines)
    markers = [i for i, line in enumerate(lines) if ERROR_MARKER.search(line)]
    following = [m for m in markers if m >= start]
    if not markers:
        return "no error marker"
    if not following:
        return "chunk after last marker"
    if following[0] - end > cfg["context_before_error"]:
        return "chunk far before marker"
    if len(chunk_lines) > cfg["context_before_error"]:
        return "chunk longer than window"
    if any(len(line) > cfg["max_line_chars"] for line in chunk_lines):
        return "line truncated"
    return "trimmed by line budget"


def evaluate_excerpts(cfg: dict) -> pd.DataFrame:
    split = read_split() or {"train": [], "test": []}
    side = {sid: name for name in ("train", "test") for sid in split[name]}
    rows = []
    for record in read_manifest().values():
        if record.get("source") != "logchunks" or record.get("status") != "ok":
            continue
        sid = record["sample_id"]
        raw_text = gzip.decompress(raw_path(sid).read_bytes()).decode("utf-8", "replace")
        excerpt = build_excerpt(raw_text, cfg)
        excerpt_text = "\n".join(normalize_line(line) for line in excerpt.splitlines())
        chunk_lines = [line for line in map(normalize_line, record["chunk"].splitlines()) if line]
        found = sum(line in excerpt_text for line in chunk_lines)
        coverage = found / len(chunk_lines) if chunk_lines else 1.0
        rows.append({
            "sample_id": sid, "split": side.get(sid, "unlabelled"), "coverage": coverage,
            "full": coverage == 1.0, "excerpt_lines": len(excerpt.splitlines()), "excerpt_chars": len(excerpt),
            "reason": "covered" if coverage == 1.0 else diagnose(chunk_lines, raw_text, cfg),
        })
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("split").agg(
        samples=("sample_id", "size"), full_coverage=("full", "mean"), line_coverage=("coverage", "mean"),
        median_lines=("excerpt_lines", "median"), median_chars=("excerpt_chars", "median"),
    )


def main(argv: list[str] | None = None) -> None:
    config = load_config()
    parser = argparse.ArgumentParser(prog="python -m ci_classifier excerpt-eval", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override an [excerpt] setting, e.g. --set strategy=hints --set hint_budget=80")
    args = parser.parse_args(argv)

    cfg = excerpt_settings(config)
    for item in args.set:
        key, _, value = item.partition("=")
        if key not in cfg:
            parser.error(f"unknown [excerpt] setting {key!r}")
        cfg[key] = value if isinstance(cfg[key], str) else type(cfg[key])(value)
    print(f"profile: {excerpt_profile()}; overrides: {', '.join(args.set) or 'none'}")

    df = evaluate_excerpts(cfg)
    print(summarize(df).round(3).to_string())
    reasons = Counter(df["reason"])
    print("\nreasons: " + ", ".join(f"{name}={reasons[name]}" for name in REASONS if reasons[name]))


if __name__ == "__main__":
    main()
