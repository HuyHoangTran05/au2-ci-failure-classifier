import json

import numpy as np
import pytest

from ci_classifier import agreement, common, label
from ci_classifier.common import DRAFT_LABELER


@pytest.fixture
def data_files(tmp_path, monkeypatch):
    monkeypatch.setattr(agreement, "BLIND_LABELS", tmp_path / "blind.jsonl")
    monkeypatch.setattr(agreement, "LABELS", tmp_path / "labels.jsonl")
    monkeypatch.setattr(common, "LABELS", tmp_path / "labels.jsonl")
    return tmp_path


def test_blind_queue_is_stable_deduplicates_chunks_and_skips_done():
    manifest = {f"s{i}": {"chunk": "same error" if i < 3 else ""} for i in range(10)}
    ids = list(manifest)
    first = agreement.blind_queue(ids, manifest, set(), count=5, seed=42)
    assert first == agreement.blind_queue(list(reversed(ids)), manifest, set(), count=5, seed=42)
    assert len(first) == 5
    assert sum(sid in ("s0", "s1", "s2") for sid in first) <= 1          # identical chunks count once
    assert agreement.blind_queue(ids, manifest, {first[0]}, count=5, seed=42) == first[1:]


def test_original_drafts_ignore_later_reviews(data_files):
    rows = [{"sample_id": "a", "label": "other", "labeler": DRAFT_LABELER},
            {"sample_id": "a", "label": "dependency", "labeler": "human", "note": "adjudicated by x"}]
    (data_files / "labels.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert agreement.original_drafts() == {"a": "other"}


def test_kappa_and_agreement_interval():
    draft = ["a", "a", "b", "b", "c", "c"]
    blind = ["a", "a", "b", "c", "c", "c"]
    assert agreement.kappa(np.array(draft), np.array(draft), ["a", "b", "c"]) == 1.0
    result = agreement.compare(draft, blind, ["g1", "g1", "g2", "g2", "g3", "g3"], ["a", "b", "c"], 200, 1)
    assert result["n"] == 6
    assert result["agreement"] == pytest.approx(5 / 6)
    assert 0 < result["kappa"] < 1
    assert result["kappa_low"] <= result["kappa"] <= result["kappa_high"]


def test_speed_warning_only_for_hasty_rounds():
    assert agreement.speed_warning([]) is None
    assert agreement.speed_warning([20.0, 40.0, 60.0]) is None
    assert "median 6.0 s" in agreement.speed_warning([3.0, 6.0, 9.0])


def test_method_bias_counts_matches_against_each_label_set():
    table = agreement.method_bias({"llm": ["a", "b", "a"]}, draft=["a", "b", "b"], blind=["a", "a", "b"])
    row = table.iloc[0]
    assert row["accuracy_vs_draft"] == pytest.approx(2 / 3)
    assert row["accuracy_vs_blind"] == pytest.approx(1 / 3)
    assert (row["only_draft_match"], row["only_blind_match"]) == (1, 0)


def test_adjudication_queue_needs_disagreement_and_no_prior_adjudication():
    blind = {"a": {"label": "other"}, "b": {"label": "dependency"}, "c": {"label": None}, "d": {"label": "other"}}
    drafts = {"a": "other", "b": "compilation", "c": "other", "d": "compilation"}
    labels = {"a": {"note": ""}, "b": {"note": "reviewed"}, "c": {"note": ""},
              "d": {"note": "adjudicated by x: draft=compilation, blind=other"}}
    assert agreement.adjudication_queue(blind, drafts, labels) == ["b"]


def test_run_blind_stores_labels_skips_and_never_touches_labels(data_files, monkeypatch, capsys):
    manifest = {sid: {"repo": "o/r", "workflow": "CI", "title": "t", "chunk": "boom", "url": ""} for sid in ("x", "y")}
    answers = iter(["2", "", "s"])            # x: category 2 with empty note; y: skip
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert label.run_blind(["x", "y"], manifest, ["compilation", "test_assertion"], "me") == 2

    stored = agreement.read_blind("me")
    assert stored["x"]["label"] == "test_assertion" and stored["x"]["protocol"] == agreement.BLIND_PROTOCOL
    assert stored["y"]["label"] is None
    assert not (data_files / "labels.jsonl").exists()
    assert "Nhãn nháp" not in capsys.readouterr().out
