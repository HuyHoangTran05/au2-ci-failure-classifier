import json
import math

import pytest

from ci_classifier import rules
from ci_classifier.classify import main as classify_main
from ci_classifier.common import ROOT, UNKNOWN, load_config, runbook_for
from ci_classifier.evaluate import compute_metrics, render_report, triage_summary
from ci_classifier.excerpt import build_excerpt, is_gh_log, parse_jobs
from ci_classifier.fetch import is_permanent, select_runs
from ci_classifier.split import extend_split, make_split

EXCERPT_CFG = {
    "context_before_error": 3,
    "tail_lines_without_marker": 2,
    "max_key_lines": 5,
    "max_lines_per_job": 20,
    "max_total_lines": 50,
    "max_line_chars": 200,
}


def log_line(job: str, text: str) -> str:
    return f"{job}\tUNKNOWN STEP\t﻿2026-06-30T19:19:33.0010720Z {text}"


# --- excerpt ---------------------------------------------------------------------------------

def test_parse_jobs_strips_timestamp_and_ansi():
    raw = "\n".join([
        log_line("build", "\x1b[31mred text\x1b[0m"),
        log_line("test", "^[[1;31m1 test failed:^[[0m"),
    ])
    assert parse_jobs(raw) == {"build": ["red text"], "test": ["1 test failed:"]}


def test_excerpt_keeps_context_before_error_marker_and_distant_key_lines():
    lines = ["src/a.cs(3,1): error CS1002: ; expected"] + [f"noise {i}" for i in range(10)]
    lines += ["near 1", "near 2", "near 3", "##[error]Process completed with exit code 1."]
    excerpt = build_excerpt("\n".join(log_line("build", t) for t in lines), EXCERPT_CFG)
    assert "error CS1002" in excerpt
    assert "near 1" in excerpt
    assert "noise 5" not in excerpt


def test_plain_logs_with_tabs_are_not_split_into_fake_jobs():
    raw = "make\tall\tfoo\n\x1b[31mtravis_fold:end:install\x1b[0K\nDone. Your build exited with 1."
    assert not is_gh_log(raw)
    assert parse_jobs(raw) == {"log": ["make\tall\tfoo", "", "Done. Your build exited with 1."]}


def test_travis_failed_command_counts_as_error_marker():
    lines = ["noise"] * 10 + ["cause of failure", "\x1b[31;1mThe command \"make test\" exited with 2.\x1b[0m"]
    lines += [f"cleanup {i}" for i in range(10)] + ["Done. Your build exited with 1."]
    excerpt = build_excerpt("\n".join(lines), EXCERPT_CFG)
    assert "cause of failure" in excerpt
    assert "cleanup 9" not in excerpt


def test_excerpt_uses_tail_when_no_error_marker():
    excerpt = build_excerpt("\n".join(log_line("job", f"line {i}") for i in range(10)), EXCERPT_CFG)
    assert "line 9" in excerpt
    assert "line 7" not in excerpt


# --- rules -----------------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("Program.cs(10,5): error CS1002: ; expected", "compilation"),
    ("npm ERR! code ERESOLVE", "dependency"),
    ("Error: Bad credentials", "authentication"),
    ("System.IO.IOException: No space left on device", "infrastructure"),
    ("Assert.Equal() Failure: Expected 5, Actual 4", "test_assertion"),
    ("all good here", UNKNOWN),
])
def test_rules_categories(text, expected):
    assert rules.classify(text)[0] == expected


def test_rules_priority_and_evidence():
    text = "restore\nerror NU1101: Unable to find package Foo\nBuild FAILED."
    assert rules.classify(text) == ("dependency", "error NU1101: Unable to find package Foo")


def test_rule_categories_exist_in_config():
    assert {category for category, _ in rules.RULES} <= set(load_config()["categories"])


def test_every_category_links_an_existing_runbook():
    config = load_config()
    for category in [*config["categories"], UNKNOWN]:
        assert (ROOT / runbook_for(category, config)).is_file(), category


# --- fetch -----------------------------------------------------------------------------------

def test_select_runs_caps_each_workflow():
    runs = [{"workflowName": "CI"}] * 5 + [{"workflowName": "Lint"}] * 5
    chosen = select_runs(runs, runs_per_repo=10, max_per_workflow=2)
    assert [r["workflowName"] for r in chosen] == ["CI", "CI", "Lint", "Lint"]


def test_expired_logs_are_permanent_errors():
    assert is_permanent("failed to get run log: log not found")
    assert not is_permanent("HTTP 502: Server Error")


# --- split -----------------------------------------------------------------------------------

@pytest.fixture
def manifest():
    return {f"s{i}": {"repo": f"org/repo{i % 4}", "workflow": "CI" if i % 2 else "Lint"} for i in range(40)}


def test_split_groups_never_straddle_train_and_test(manifest):
    split = make_split(list(manifest), manifest, 0.3, seed=1)
    group = lambda sid: (manifest[sid]["repo"], manifest[sid]["workflow"])
    assert not {group(s) for s in split["train"]} & {group(s) for s in split["test"]}
    assert len(split["train"]) + len(split["test"]) == 40


def test_stratified_split_puts_every_label_in_test(manifest):
    # "rare" appears in only two groups; a random fill could leave it all in train.
    # Lint runs only have even ids, so they live in repo0 and repo2.
    label_of = {sid: ("rare" if manifest[sid]["repo"] in ("org/repo0", "org/repo2") and manifest[sid]["workflow"] == "Lint"
                      else "common") for sid in manifest}
    split = make_split(list(manifest), manifest, 0.3, seed=1, label_of=label_of)
    test_labels = {label_of[sid] for sid in split["test"]}
    assert test_labels == {"rare", "common"}
    group = lambda sid: (manifest[sid]["repo"], manifest[sid]["workflow"])
    assert not {group(s) for s in split["train"]} & {group(s) for s in split["test"]}


def test_extend_split_keeps_existing_assignments(manifest):
    split = make_split([f"s{i}" for i in range(30)], manifest, 0.3, seed=1)
    before_test = list(split["test"])
    assert extend_split(split, list(manifest), manifest) == 10
    assert split["test"][: len(before_test)] == before_test


# --- evaluate --------------------------------------------------------------------------------

def test_metrics_precision_recall_and_abstention():
    y_true = ["compilation", "compilation", "test_assertion", "test_assertion", "dependency"]
    y_pred = ["compilation", UNKNOWN, "compilation", "test_assertion", UNKNOWN]
    m = compute_metrics(y_true, y_pred, ["compilation", "test_assertion", "dependency", "other"])
    per = m["per_category"]

    assert m["summary"]["accuracy"] == pytest.approx(0.4)
    assert m["summary"]["abstention_rate"] == pytest.approx(0.4)
    assert per.loc["compilation", "precision"] == pytest.approx(0.5)
    assert per.loc["compilation", "recall"] == pytest.approx(0.5)
    assert per.loc["test_assertion", "precision"] == pytest.approx(1.0)
    assert per.loc["dependency", "f1"] == 0.0          # occurs, never predicted
    assert math.isnan(per.loc["other", "f1"])           # never occurs, never predicted
    assert m["confusion"].loc["compilation"].to_dict() == {
        "compilation": 1, "test_assertion": 0, "dependency": 0, "other": 0, UNKNOWN: 1}


def test_triage_summary_and_report_render():
    records = [
        {"sample_id": "a", "participant": "p", "condition": "A", "seconds": 30.0, "correct": True},
        {"sample_id": "b", "participant": "p", "condition": "B", "seconds": 10.0, "correct": True},
        {"sample_id": "c", "participant": "p", "condition": "B", "seconds": 20.0, "correct": False},
    ]
    table = triage_summary(records)
    assert table.loc["B - log + classifier hint", "median_seconds"] == 15.0
    assert table.loc["B - log + classifier hint", "accuracy"] == 0.5

    metrics = compute_metrics(["compilation"], ["compilation"], ["compilation"])
    metrics["summary"]["ms_per_sample"] = 1.0
    report = render_report({
        "run": {"created_at": "now", "train_samples": 1, "test_samples": 1, "test_label_counts": {"compilation": 1},
                "labels_sha256": "abc", "split_created_at": "now"},
        "small_test_set": 30,
        "methods": [{"title": "Rules", "summary": metrics["summary"],
                     "per_category": metrics["per_category"].reset_index().to_dict("records"),
                     "confusion_columns": list(metrics["confusion"].columns),
                     "confusion_rows": [(k, v.tolist()) for k, v in metrics["confusion"].iterrows()],
                     "mistakes": []}],
        "triage": table.reset_index().to_dict("records"),
    })
    assert "| compilation | 1.00 | 1.00 | 1.00 | 1 | 1 |" in report
    assert "| B - log + classifier hint | 2 | 1 | 15.00 | 15.00 | 0.50 |" in report


# --- classify CLI ----------------------------------------------------------------------------

def test_classify_saved_log_links_runbook(tmp_path, capsys):
    log = tmp_path / "job.log"
    log.write_text(log_line("build", "src/app.ts(1,1): error TS2304: Cannot find name 'x'.") + "\n"
                   + log_line("build", "##[error]Process completed with exit code 2."), encoding="utf-8")
    classify_main([str(log), "--json"])
    result = json.loads(capsys.readouterr().out)
    assert result["category"] == "compilation"
    assert result["runbook"] == "docs/runbooks/compilation.md"
