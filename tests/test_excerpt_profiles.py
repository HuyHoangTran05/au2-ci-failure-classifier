import pytest

from ci_classifier import common
from ci_classifier.excerpt import build_excerpt, hint_excerpt

CONFIG = {"excerpt": {"strategy": "marker", "context_before_error": 40,
                      "profiles": {"wide": {"context_before_error": 80}}}}
HINT_CFG = {"strategy": "hints", "max_line_chars": 200, "hint_budget": 12, "hint_gap": 3, "hint_padding": 1,
            "hint_key_weight": 3, "hint_recency_weight": 2, "hint_anchor_lines": 2,
            "max_lines_per_job": 120, "max_total_lines": 300}


def test_default_profile_uses_base_settings_and_directory(monkeypatch):
    monkeypatch.delenv("CI_EXCERPT_PROFILE", raising=False)
    assert common.excerpt_settings(CONFIG) == {"strategy": "marker", "context_before_error": 40}
    assert common.excerpt_dir() == common.EXCERPT_DIR


def test_named_profile_overrides_settings_and_uses_own_directory(monkeypatch):
    monkeypatch.setenv("CI_EXCERPT_PROFILE", "wide")
    assert common.excerpt_settings(CONFIG)["context_before_error"] == 80
    assert common.excerpt_dir().name == "excerpts-wide"
    assert common.excerpt_path("s1").parent.name == "excerpts-wide"


def test_unknown_profile_is_rejected(monkeypatch):
    monkeypatch.setenv("CI_EXCERPT_PROFILE", "nope")
    with pytest.raises(SystemExit):
        common.excerpt_settings(CONFIG)


def test_hint_excerpt_keeps_distant_error_block_and_last_marker():
    lines = (["setup step"] * 20 + ["AssertionError: expected 1 got 2", "  at test_x (t.py:3)"]
             + ["cleanup output"] * 60 + ['The command "make test" exited with 1.'])
    out = hint_excerpt(lines, HINT_CFG)
    assert "AssertionError: expected 1 got 2" in out
    assert 'The command "make test" exited with 1.' in out
    assert "[...]" in out
    assert len([line for line in out if line not in ("-- context --", "[...]")]) <= HINT_CFG["hint_budget"]


def test_line_template_ignores_run_specific_values():
    from ci_classifier.excerpt import line_template
    a = line_template("Restored /home/runner/work/app/app.csproj (in 4.43 sec) id 3fa85f64-5717-4562-b3fc-2c963f66afa6")
    b = line_template("Restored /home/runner/work/app/other.csproj (in 12 sec) id 9d1b2c3e-1111-2222-3333-444455556666")
    assert a == b


def test_baseline_diff_drops_lines_seen_in_success_run_but_keeps_markers():
    from ci_classifier.excerpt import novel_lines
    failed = ["Run npm ci", "added 812 packages in 21s", "FAIL src/app.test.ts", "Expected 2, received 3",
              "##[error]Process completed with exit code 1."]
    success = ["2026-09-01T10:00:00.0000000Z Run npm ci", "2026-09-01T10:00:01.0000000Z added 790 packages in 19s",
               "2026-09-01T10:00:02.0000000Z ##[error]Process completed with exit code 1."]
    assert novel_lines(failed, success) == ["FAIL src/app.test.ts", "Expected 2, received 3",
                                            "##[error]Process completed with exit code 1."]


def test_build_excerpt_uses_baseline_only_for_matching_jobs():
    ts = "2026-09-14T04:48:39.1010000Z"
    raw = "\n".join(f"{job}\tstep\t{ts} {text}" for job, text in [
        ("build", "setup ok"), ("build", "real failure line"), ("build", "##[error]Process completed with exit code 1."),
        ("lint", "setup ok"), ("lint", "##[error]Process completed with exit code 1."),
    ])
    cfg = {"strategy": "baseline-diff", "context_before_error": 40, "tail_lines_without_marker": 40,
           "max_key_lines": 5, "max_lines_per_job": 120, "max_total_lines": 300, "max_line_chars": 200}
    excerpt = build_excerpt(raw, cfg, baseline={"build": ["setup ok"]})
    build_part, lint_part = excerpt.split("## job: lint")
    assert "setup ok" not in build_part and "real failure line" in build_part
    assert "setup ok" in lint_part                               # no baseline for lint: marker window unchanged


def test_build_excerpt_dispatches_on_strategy():
    raw = "\n".join(["noise"] * 10 + ["fatal: could not read Username", 'The command "git push" exited with 128.'])
    assert "fatal: could not read Username" in build_excerpt(raw, HINT_CFG)
