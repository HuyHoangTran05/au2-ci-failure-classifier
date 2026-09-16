import json

import pytest

from ci_classifier import llm

CONFIG = {"categories": ["compilation", "other"],
          "llm": {"model": "m", "max_excerpt_chars": 1000, "abstain_below": 0, "max_tokens": 2560}}


def test_v1_is_one_system_and_one_user_message():
    messages = llm.build_messages("log", CONFIG["categories"], 1000, "v1")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "log" in messages[-1]["content"]


def test_v2_adds_rules_and_labelled_examples():
    messages = llm.build_messages("log", CONFIG["categories"], 1000, "v2")
    assert [m["role"] for m in messages] == ["system"] + ["user", "assistant"] * len(llm.FEW_SHOT_V2) + ["user"]
    assert "easy to get wrong" in messages[0]["content"]
    answers = [json.loads(m["content"])["category"] for m in messages if m["role"] == "assistant"]
    assert answers == [category for _, category, _, _ in llm.FEW_SHOT_V2]
    assert messages[-1]["content"].endswith("```")


def test_unknown_version_is_rejected():
    with pytest.raises(ValueError):
        llm.build_messages("log", CONFIG["categories"], 1000, "v3")


def test_active_version_comes_from_config():
    assert llm.active_version(CONFIG) == "v1"
    assert llm.active_version({"llm": {**CONFIG["llm"], "prompt_version": "v2"}}) == "v2"


def test_stored_answers_are_keyed_by_version(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "PREDICTIONS", tmp_path / "p.jsonl")

    class FakeClient:
        model = "m"

        def complete(self, messages):
            return {"content": '{"category": "other", "evidence": "e", "confidence": 1}', "model": "m",
                    "usage": {}, "latency_s": 0.1}

    llm.classify_text("log", CONFIG, FakeClient(), "s1", "v2")
    assert llm.cached_predictor(CONFIG, version="v2")("log")[0] == "other"
    assert llm.cached_predictor(CONFIG, version="v1")("log") is None      # v1 must not reuse a v2 answer
