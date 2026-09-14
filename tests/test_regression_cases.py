"""Real log snippets the keyword rules must keep classifying correctly.

Add a case to regression_cases.jsonl whenever you fix a misclassification, so it cannot silently
come back. Cases marked "known_gap" document failures not fixed yet; they are strict xfails, so the
test run tells you when a rule change fixes one (then remove the flag).
"""

import json
from pathlib import Path

import pytest

from ci_classifier import rules

CASES_FILE = Path(__file__).with_name("regression_cases.jsonl")
CASES = [json.loads(line) for line in CASES_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("case", [
    pytest.param(case, id=case["id"],
                 marks=pytest.mark.xfail(strict=True, reason="known gap") if case.get("known_gap") else ())
    for case in CASES
])
def test_regression_case(case):
    category, evidence = rules.classify(case["text"])
    assert category == case["expected"], f"evidence: {evidence!r} (source: {case['source']})"
