import json

import pytest

from ci_classifier.common import append_jsonl, read_jsonl, repair_partial_tail


def test_append_after_interrupted_write_drops_only_the_broken_record(tmp_path, capsys):
    path = tmp_path / "data.jsonl"
    append_jsonl(path, {"id": 1, "text": "tiếng Việt"})
    with path.open("a", encoding="utf-8") as f:
        f.write('{"id": 2, "text": "cut off mid-wri')          # power cut: no closing quote, no newline

    assert read_jsonl(path) == [{"id": 1, "text": "tiếng Việt"}]  # reading tolerates the broken tail
    append_jsonl(path, {"id": 3})
    assert read_jsonl(path) == [{"id": 1, "text": "tiếng Việt"}, {"id": 3}]
    assert "incomplete" in capsys.readouterr().err


def test_repair_leaves_complete_files_alone(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text(json.dumps({"id": 1}) + "\n", encoding="utf-8")
    assert repair_partial_tail(path) == 0
    assert repair_partial_tail(tmp_path / "missing.jsonl") == 0


def test_invalid_line_in_the_middle_still_raises(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text('{"id": 1}\nnot json\n{"id": 2}\n', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        read_jsonl(path)
