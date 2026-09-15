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


def test_build_excerpt_dispatches_on_strategy():
    raw = "\n".join(["noise"] * 10 + ["fatal: could not read Username", 'The command "git push" exited with 128.'])
    assert "fatal: could not read Username" in build_excerpt(raw, HINT_CFG)
