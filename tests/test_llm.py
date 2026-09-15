import io
import json
import urllib.error

import pytest

from ci_classifier import llm
from ci_classifier.common import UNKNOWN

CATEGORIES = ["compilation", "test_assertion", "dependency", "authentication", "infrastructure", "other"]
CFG = {
    "base_url": "https://example.invalid/chat", "model": "test/model:free", "temperature": 0, "max_tokens": 100,
    "timeout_seconds": 5, "requests_per_minute": 60, "max_retries": 2, "max_excerpt_chars": 50,
    "abstain_below": 0.0,
}


@pytest.mark.parametrize("content, expected", [
    ('{"category": "compilation", "evidence": "error TS2345", "confidence": 0.9}', ("compilation", "error TS2345", 0.9)),
    ('Sure!\n```json\n{"category": "Dependency", "evidence": "npm ERR!", "confidence": "0.7"}\n```',
     ("dependency", "npm ERR!", 0.7)),
    ('<think>maybe {"category": "other"}</think>{"category": "infrastructure", "evidence": "ECONNRESET"}',
     ("infrastructure", "ECONNRESET", None)),
    ('{"category": "flaky", "evidence": "x", "confidence": 0.5}', (UNKNOWN, "x", 0.5)),
    ('{"category": "authentication", "evidence": "{\\"errors\\":[\\"permission denied\\"]}", "confidence": 0.95}',
     ("authentication", '{"errors":["permission denied"]}', 0.95)),
    ("I cannot tell.", (UNKNOWN, "unparseable reply", None)),
])
def test_parse_response(content, expected):
    assert llm.parse_response(content, CATEGORIES) == expected


def test_build_messages_lists_categories_and_keeps_log_tail():
    messages = llm.build_messages("HEAD" + "x" * 100 + "TAIL", CATEGORIES, max_chars=50)
    assert "authentication:" in messages[0]["content"] and "unknown:" in messages[0]["content"]
    assert "TAIL" in messages[1]["content"] and "HEAD" not in messages[1]["content"]


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code: int, body: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.invalid", code, "err", {}, io.BytesIO(body.encode()))


def make_client(replies):
    replies = iter(replies)

    def opener(request, timeout):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(json.dumps(reply).encode())

    return llm.OpenRouterClient(CFG, "key", opener=opener, sleep=lambda s: None, clock=lambda: 0.0)


def test_client_retries_rate_limit_then_returns_content():
    ok = {"model": "test/model:free", "choices": [{"message": {"content": "{}"}}],
          "usage": {"prompt_tokens": 10, "completion_tokens": 2}}
    client = make_client([http_error(429, "rate limited per minute"), ok])
    reply = client.complete([])
    assert reply["content"] == "{}" and reply["usage"]["prompt_tokens"] == 10


def test_client_retries_connection_reset():
    ok = {"choices": [{"message": {"content": "{}"}}], "usage": {}}
    client = make_client([ConnectionResetError(10054, "forcibly closed"), ok])
    assert client.complete([])["content"] == "{}"


def test_client_stops_on_daily_limit_and_auth_errors():
    with pytest.raises(llm.DailyLimitReached):
        make_client([http_error(429, "Rate limit exceeded: free-models-per-day")]).complete([])
    with pytest.raises(llm.LLMError):
        make_client([http_error(401, "No auth credentials found")]).complete([])


def test_classify_text_stores_answer_and_cached_predictor_reads_it(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "PREDICTIONS", tmp_path / "llm_predictions.jsonl")
    reply = {"model": "test/model:free", "usage": {"prompt_tokens": 5, "completion_tokens": 3, "cost": 0},
             "choices": [{"message": {"content": '{"category": "other", "evidence": "lint", "confidence": 0.3}'}}]}
    config = {"categories": CATEGORIES, "llm": CFG}
    record = llm.classify_text("some log", config, make_client([reply]), "s1")
    assert record["category"] == "other" and record["sample_id"] == "s1"

    predict = llm.cached_predictor(config)
    assert predict("some log") == ("other", "conf=0.30 | lint")
    assert predict("a different log") is None

    strict = llm.cached_predictor({"categories": CATEGORIES, "llm": {**CFG, "abstain_below": 0.5}})
    assert strict("some log")[0] == UNKNOWN


def test_load_api_key_reads_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(llm, "ROOT", tmp_path)
    (tmp_path / ".env").write_text('OPENROUTER_API_KEY="abc123"\n', encoding="utf-8")
    assert llm.load_api_key() == "abc123"
