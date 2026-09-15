"""Command line entry point: python -m ci_classifier <command> [options]."""

from __future__ import annotations

import sys
from importlib import import_module

COMMANDS = {
    "fetch": "download logs of failed GitHub Actions runs",
    "import-logchunks": "import the LogChunks data set (Travis CI logs with marked failure chunks)",
    "fetch-baselines": "download the last successful run of each failed GitHub Actions sample",
    "excerpt": "cut raw logs down to the lines that explain the failure",
    "excerpt-eval": "measure how well excerpts keep LogChunks' marked failure chunks",
    "label": "label excerpts by hand",
    "split": "split labelled samples into train and test sets",
    "rules": "inspect keyword-rule predictions on the train set",
    "tune-tfidf": "choose the TF-IDF abstain threshold by cross-validation on the train set",
    "llm-run": "ask the LLM (OpenRouter) about test samples and store the answers",
    "evaluate": "compare classifiers on the test set and write a report",
    "classify": "classify one saved failed-job log and link its runbook",
    "triage": "time human triage with and without the classifier's hint",
}
# Commands whose module name differs from the command name.
MODULES = {"import-logchunks": "logchunks", "llm-run": "llm", "excerpt-eval": "excerpt_eval",
           "fetch-baselines": "baselines", "tune-tfidf": "tune_tfidf"}


def main() -> None:
    # Windows defaults redirected output to cp1252, which cannot print Vietnamese prompts or log emoji.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("usage: python -m ci_classifier <command> [options]\n\ncommands:")
        for name, description in COMMANDS.items():
            print(f"  {name:<9} {description}")
        print("\nRun `python -m ci_classifier <command> -h` for a command's options.")
        raise SystemExit(0 if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help") else 2)
    module = MODULES.get(sys.argv[1], sys.argv[1])
    import_module(f"ci_classifier.{module}").main(sys.argv[2:])


if __name__ == "__main__":
    main()
