"""Classify one saved failed-job log and point to the matching runbook.

Usage:
    gh run view <run-id> -R owner/repo --log-failed > job.log
    python -m ci_classifier classify job.log
    python -m ci_classifier classify job.log --method tfidf --json

Accepts plain text or .gz logs, in `gh run view --log-failed` format or as raw job output.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from .common import excerpt_settings, load_config, read_labels, read_split, runbook_for
from .excerpt import build_excerpt
from .methods import METHODS, build_predictor


def load_log(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix == ".gz":
        data = gzip.decompress(data)
    return data.decode("utf-8", "replace")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier classify", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log", type=Path, help="saved failed-job log (.log, .txt or .gz)")
    parser.add_argument("--method", choices=METHODS, default="rules")
    parser.add_argument("--json", action="store_true", help="print a machine-readable result")
    parser.add_argument("--show-excerpt", action="store_true", help="also print the lines the decision used")
    args = parser.parse_args(argv)

    config = load_config()
    try:
        predict = build_predictor(args.method, config, read_labels(), read_split(), live=True)
        excerpt = build_excerpt(load_log(args.log), excerpt_settings(config))
        category, detail = predict(excerpt)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")
    result = {"log": str(args.log), "method": args.method, "category": category,
              "detail": detail, "runbook": runbook_for(category, config)}

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Category: {category}")
        print(f"Evidence: {detail or '-'}")
        print(f"Runbook:  {result['runbook'] or '-'}")
    if args.show_excerpt:
        print("\n" + excerpt)


if __name__ == "__main__":
    main()
