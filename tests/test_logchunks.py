import io
import zipfile

import builtins

from ci_classifier import label
from ci_classifier.label import chunk_key
from ci_classifier.logchunks import chunk_coverage, iter_examples

XML = """<?xml version="1.0" encoding="UTF-8"?>
<Examples>
  <Example>
    <Log>C/git@git/failed/564416725.log</Log>
    <Keywords>not defined, -trace2_event_file, </Keywords>
    <Category>0</Category>
    <Chunk>flag provided but not defined: -trace2_event_file</Chunk>
  </Example>
</Examples>
"""


def make_archive() -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("LogChunks/build-failure-reason/C/git@git.xml", XML)
        archive.writestr("LogChunks/logs/C/git@git/failed/564416725.log", "build\nflag provided but not defined\n")
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


def test_iter_examples_reads_chunk_and_log():
    [example] = list(iter_examples(make_archive()))
    assert example["language"] == "C"
    assert example["repo"] == "git/git"
    assert example["job_id"] == "564416725"
    assert example["keywords"] == ["not defined", "-trace2_event_file"]
    assert example["chunk"] == "flag provided but not defined: -trace2_event_file"
    assert example["log"].startswith(b"build")


def test_chunk_coverage_ignores_ansi_and_whitespace():
    excerpt = "-- context --\nstep one\n  Failed   1/13 subtests\n"
    assert chunk_coverage("\x1b[31mFailed 1/13 subtests\x1b[0m", excerpt) == 1.0
    assert chunk_coverage("Failed 1/13 subtests\nmissing line", excerpt) == 0.5


def answer_with(monkeypatch, *answers):
    replies = iter(answers)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(replies))
    monkeypatch.setattr(label, "show", lambda *args, **kwargs: None)


def test_review_enter_keeps_draft(monkeypatch):
    answer_with(monkeypatch, "")
    draft = {"label": "other", "note": "lint"}
    assert label.ask("s1", {"url": ""}, ["compilation", "other"], "[1/1]", draft) == ("other", "reviewed: kept draft")


def test_review_number_changes_draft_and_records_it(monkeypatch):
    answer_with(monkeypatch, "1", "")
    draft = {"label": "other", "note": "lint"}
    result = label.ask("s1", {"url": ""}, ["compilation", "other"], "[1/1]", draft)
    assert result == ("compilation", "reviewed: changed from other")


def test_review_number_equal_to_draft_counts_as_kept(monkeypatch):
    answer_with(monkeypatch, "2", "")
    draft = {"label": "other", "note": "lint"}
    assert label.ask("s1", {"url": ""}, ["compilation", "other"], "[1/1]", draft) == ("other", "reviewed: kept draft")


def test_accept_drafts_keeps_label_and_marks_reviewer(tmp_path, monkeypatch):
    from ci_classifier import common
    monkeypatch.setattr(common, "LABELS", tmp_path / "labels.jsonl")
    common.append_label("d1", "other", "lint", labeler=common.DRAFT_LABELER)
    common.append_label("d2", "compilation", "tsc", labeler=common.DRAFT_LABELER)
    common.append_label("h1", "dependency", "npm")

    count = label.accept_drafts(common.read_labels(), lambda sid: sid != "d2", "hoang")
    after = common.read_labels()
    assert count == 1
    assert after["d1"]["labeler"] == common.HUMAN and after["d1"]["label"] == "other"
    assert "bulk accepted by hoang" in after["d1"]["note"]
    assert after["d2"]["labeler"] == common.DRAFT_LABELER


def test_chunk_key_matches_identical_chunks_only():
    assert chunk_key({"chunk": "a  b\nc"}) == chunk_key({"chunk": "a b c"})
    assert chunk_key({"chunk": "a b"}) != chunk_key({"chunk": "a c"})
    assert chunk_key({}) == ""
