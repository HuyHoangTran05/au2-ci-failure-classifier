import pytest

from ci_classifier import llm, panel
from ci_classifier.common import UNKNOWN
from ci_classifier.label import shuffled_candidates

MODELS = ["a/one:free", "b/two:free", "c/three:free"]


def test_panel_prompt_shows_what_a_human_sees_and_nothing_else():
    record = {"repo": "o/r", "workflow": "travis-ci", "title": "log.txt", "chunk": "boom: failed\n",
              "label": "SECRET_LABEL", "note": "SECRET_NOTE"}
    messages = panel.build_panel_messages(record, "line 1\nline 2\n", max_chars=1000)
    text = " ".join(m["content"] for m in messages)
    assert "boom: failed" in text and "line 2" in text and "repo: o/r" in text
    assert "SECRET" not in text
    assert panel.input_sha(messages) == panel.input_sha(panel.build_panel_messages(record, "line 1\nline 2\n", 1000))


def test_panel_prompt_keeps_the_end_of_long_excerpts():
    messages = panel.build_panel_messages({}, "head\n" + "x" * 50 + "tail", max_chars=20)
    assert "tail" in messages[1]["content"] and "head" not in messages[1]["content"]


@pytest.mark.parametrize("votes, draft, expected", [
    ({"a/one:free": "other", "b/two:free": "other", "c/three:free": "dependency"}, "other", ("confirmed", "other")),
    ({"a/one:free": "compilation", "b/two:free": "compilation", "c/three:free": "other"}, "other",
     ("contested", "compilation")),
    ({"a/one:free": "compilation", "b/two:free": "other", "c/three:free": "dependency"}, "other", ("split", None)),
    ({"a/one:free": "other", "b/two:free": UNKNOWN, "c/three:free": UNKNOWN}, "other", ("split", None)),
    ({"a/one:free": "other", "b/two:free": "other"}, "other", ("incomplete", "other")),
])
def test_decide_buckets(votes, draft, expected):
    assert panel.decide(votes, draft, MODELS) == expected


def test_fleiss_kappa_extremes():
    assert panel.fleiss_kappa([["a", "a", "a"], ["b", "b", "b"]], ["a", "b", "c"]) == pytest.approx(1.0)
    assert panel.fleiss_kappa([["a", "b", "c"]], ["a", "b", "c"]) == pytest.approx(-0.5)


def test_adjudication_candidates_are_distinct_and_stably_shuffled():
    first = shuffled_candidates("sample-1", ["other", "compilation", "other", "dependency"])
    assert sorted(first) == ["compilation", "dependency", "other"]
    assert first == shuffled_candidates("sample-1", ["dependency", "other", "compilation"])


def test_run_stores_answers_resumes_and_hides_labels(tmp_path, monkeypatch, capsys):
    config = {"categories": ["compilation", "other"], "split": {"seed": 1}, "evaluation": {"bootstrap_samples": 10},
              "llm": {"max_excerpt_chars": 1000, "base_url": "", "model": "x", "temperature": 0, "max_tokens": 10,
                      "timeout_seconds": 1, "requests_per_minute": 60, "max_retries": 0, "abstain_below": 0},
              "panel": {"models": MODELS[:2], "sample_count": 2, "max_tokens": 50, "requests_per_minute": 60}}
    calls = []

    class FakeClient:
        def __init__(self, cfg, key, model):
            self.model = model

        def complete(self, messages):
            calls.append(self.model)
            return {"content": '{"category": "other", "evidence": "e", "confidence": 0.9}', "model": self.model,
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "latency_s": 0.1}

    monkeypatch.setattr(panel, "PANEL_LABELS", tmp_path / "panel.jsonl")
    monkeypatch.setattr(panel, "load_config", lambda: config)
    monkeypatch.setattr(panel, "panel_samples", lambda cfg, count=None: ["s1", "s2"])
    monkeypatch.setattr(panel, "read_manifest", lambda: {"s1": {"repo": "r"}, "s2": {"repo": "r", "chunk": "c"}})
    monkeypatch.setattr(panel, "read_excerpt", lambda sid: f"log of {sid}")
    monkeypatch.setattr(llm, "load_api_key", lambda: "key")
    monkeypatch.setattr(llm, "OpenRouterClient", FakeClient)

    panel.run([])
    assert len(calls) == 4
    votes = panel.votes_for(["s1", "s2"], MODELS[:2], config)
    assert votes == {"s1": {m: "other" for m in MODELS[:2]}, "s2": {m: "other" for m in MODELS[:2]}}
    assert "label" not in capsys.readouterr().out.lower().replace("labels and predictions are hidden", "")

    panel.run([])                     # everything stored: no new calls
    assert len(calls) == 4


def test_run_stops_after_consecutive_errors_and_resumes(tmp_path, monkeypatch, capsys):
    config = {"categories": ["other"], "split": {"seed": 1}, "llm": {"max_excerpt_chars": 1000},
              "panel": {"models": MODELS[:1], "sample_count": 5, "max_tokens": 50, "requests_per_minute": 60,
                        "max_consecutive_errors": 2}}
    online = {"up": False}
    calls = []

    class FakeClient:
        def __init__(self, cfg, key, model):
            self.model = model

        def complete(self, messages):
            calls.append(1)
            if not online["up"]:
                raise llm.LLMError("gave up after 4 attempts: URLError: no network")
            return {"content": '{"category": "other", "evidence": "e", "confidence": 1}', "model": self.model,
                    "usage": {}, "latency_s": 0.1}

    monkeypatch.setattr(panel, "PANEL_LABELS", tmp_path / "panel.jsonl")
    monkeypatch.setattr(panel, "load_config", lambda: config)
    monkeypatch.setattr(panel, "panel_samples", lambda cfg, count=None: [f"s{i}" for i in range(5)])
    monkeypatch.setattr(panel, "read_manifest", lambda: {f"s{i}": {} for i in range(5)})
    monkeypatch.setattr(panel, "read_excerpt", lambda sid: f"log of {sid}")
    monkeypatch.setattr(llm, "load_api_key", lambda: "key")
    monkeypatch.setattr(llm, "OpenRouterClient", FakeClient)

    panel.run([])
    assert len(calls) == 2 and "Stopping after 2 failed calls" in capsys.readouterr().out
    online["up"] = True
    panel.run([])
    assert len(panel.votes_for([f"s{i}" for i in range(5)], MODELS[:1], config)) == 5


def test_retry_unparseable_replaces_only_failed_replies(tmp_path, monkeypatch):
    config = {"categories": ["compilation", "other"], "split": {"seed": 1},
              "llm": {"max_excerpt_chars": 1000},
              "panel": {"models": MODELS[:1], "sample_count": 2, "max_tokens": 50, "retry_max_tokens": 500,
                        "requests_per_minute": 60}}
    replies = iter(["<think>out of tokens", '{"category": "other", "evidence": "e", "confidence": 0.9}',
                    '{"category": "compilation", "evidence": "e", "confidence": 0.8}'])
    budgets = []

    class FakeClient:
        def __init__(self, cfg, key, model):
            budgets.append(cfg["max_tokens"])
            self.model = model

        def complete(self, messages):
            return {"content": next(replies), "model": self.model, "usage": {}, "latency_s": 0.1}

    monkeypatch.setattr(panel, "PANEL_LABELS", tmp_path / "panel.jsonl")
    monkeypatch.setattr(panel, "load_config", lambda: config)
    monkeypatch.setattr(panel, "panel_samples", lambda cfg, count=None: ["s1", "s2"])
    monkeypatch.setattr(panel, "read_manifest", lambda: {"s1": {}, "s2": {}})
    monkeypatch.setattr(panel, "read_excerpt", lambda sid: f"log of {sid}")
    monkeypatch.setattr(llm, "load_api_key", lambda: "key")
    monkeypatch.setattr(llm, "OpenRouterClient", FakeClient)

    panel.run([])
    assert panel.votes_for(["s1", "s2"], MODELS[:1], config) == {"s1": {MODELS[0]: UNKNOWN}, "s2": {MODELS[0]: "other"}}
    panel.run(["--retry-unparseable"])        # only s1 is asked again, with the larger budget
    assert budgets == [50, 500]
    assert panel.votes_for(["s1", "s2"], MODELS[:1], config) == {"s1": {MODELS[0]: "compilation"},
                                                                  "s2": {MODELS[0]: "other"}}
