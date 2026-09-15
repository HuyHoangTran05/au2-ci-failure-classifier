"""Baseline 3: classify failed CI logs with an LLM through OpenRouter.

Free OpenRouter models allow only a small number of requests per day, so every answer is stored in
data/llm_predictions.jsonl, keyed by (model, prompt version, excerpt hash). `evaluate` reads only that file;
it never calls the API, and it scores the LLM on the test samples that already have an answer.

The API key is read from the OPENROUTER_API_KEY environment variable or from a git-ignored `.env` file.

Usage:
    python -m ci_classifier llm-run                      # answer test samples, GitHub Actions first
    python -m ci_classifier llm-run --limit 20
    python -m ci_classifier llm-run --source github-actions   # only the target log format
    python -m ci_classifier llm-run --model nvidia/nemotron-3-super-120b-a12b:free --split train --limit 3
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Callable

from .common import (ROOT, UNKNOWN, append_jsonl, load_config, now_iso, read_excerpt, read_jsonl, read_labels,
                     read_manifest, read_split)

PREDICTIONS = ROOT / "data" / "llm_predictions.jsonl"
PROMPT_VERSION = "v1"

CATEGORY_GUIDE = {
    "compilation": "code does not compile or type-check (compiler/type-checker errors, syntax errors, "
                   "warnings treated as errors, linker errors)",
    "test_assertion": "code builds but tests produce wrong results (assertion failures, failing test cases, "
                      "a single test timing out, snapshot/baseline mismatch, test crashes)",
    "dependency": "packages or libraries cannot be installed, resolved or loaded (registry lookups, version "
                  "conflicts, lock files out of sync, missing modules, runtime/toolchain too old for a dependency)",
    "authentication": "missing or invalid credentials, tokens, secrets or permissions (401/403 from an auth "
                      "check, Bad credentials, AADSTS errors, 'Resource not accessible by integration')",
    "infrastructure": "the CI machine or network fails, not the code (runner lost, disk full, whole job "
                      "timeout, connection resets, DNS, 5xx from services, rate limits, external service outage)",
    "other": "a clear cause outside the categories above (lint/format checks, docs build, PR label or policy "
             "checks, generated files not committed, workflow script bugs)",
}

SYSTEM_PROMPT = """You triage failed CI jobs. You receive an excerpt of a failed CI log and must name the root cause.

Categories:
{categories}
- unknown: the excerpt does not contain enough evidence to decide.

Rules:
- Pick the root cause, not a consequence (a missing package that breaks the build is dependency).
- Ignore summary jobs that only report that other jobs failed.
- If several jobs fail for different reasons, pick the cause of the most important failing build or test job.
- Answer unknown rather than guess.

Reply with only a JSON object, no other text:
{{"category": "<one category name>", "evidence": "<the single log line that shows the cause, copied verbatim>", "confidence": <number from 0 to 1>}}"""


class LLMError(RuntimeError):
    pass


class DailyLimitReached(LLMError):
    pass


def load_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "OPENROUTER_API_KEY":
                key = value.strip().strip('"').strip("'")
    if not key:
        raise LLMError("No OpenRouter API key: set OPENROUTER_API_KEY or add it to .env")
    return key


def excerpt_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_messages(excerpt: str, categories: list[str], max_chars: int) -> list[dict]:
    if len(excerpt) > max_chars:
        # Keep the end: the failure markers sit at the bottom of each job's context.
        excerpt = "[... earlier lines omitted ...]\n" + excerpt[-max_chars:]
    guide = "\n".join(f"- {name}: {CATEGORY_GUIDE[name]}" for name in categories)
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(categories=guide)},
        {"role": "user", "content": f"CI log excerpt:\n```\n{excerpt}\n```"},
    ]


def parse_response(content: str, categories: list[str]) -> tuple[str, str, float | None]:
    """Extract (category, evidence, confidence) from a model reply; unparseable replies become unknown."""
    content = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL)
    decoder = json.JSONDecoder()
    # Decode a JSON value at every "{" (a regex cannot match braces nested inside the evidence string);
    # the last object with a category wins, so drafts the model rewrote are skipped.
    objects = []
    for start in (i for i, ch in enumerate(content) if ch == "{"):
        try:
            data, _ = decoder.raw_decode(content, start)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "category" in data:
            objects.append(data)
    for data in reversed(objects):
            category = str(data.get("category", "")).strip().lower()
            if category not in categories:
                category = UNKNOWN
            try:
                confidence = float(data["confidence"]) if data.get("confidence") is not None else None
            except (TypeError, ValueError):
                confidence = None
            return category, str(data.get("evidence", ""))[:300], confidence
    return UNKNOWN, "unparseable reply", None


class OpenRouterClient:
    def __init__(self, cfg: dict, api_key: str, model: str | None = None,
                 opener: Callable = urllib.request.urlopen, sleep: Callable = time.sleep,
                 clock: Callable = time.monotonic):
        self.cfg = cfg
        self.api_key = api_key
        self.model = model or cfg["model"]
        self.opener, self.sleep, self.clock = opener, sleep, clock
        self.min_interval = 60.0 / cfg["requests_per_minute"]
        self.last_request = None

    def _wait_for_slot(self) -> None:
        if self.last_request is not None:
            remaining = self.min_interval - (self.clock() - self.last_request)
            if remaining > 0:
                self.sleep(remaining)
        self.last_request = self.clock()

    def complete(self, messages: list[dict]) -> dict:
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": self.cfg["temperature"],
            "max_tokens": self.cfg["max_tokens"],
            "usage": {"include": True},
        }).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                   "X-Title": "AU2 CI failure classifier"}
        last_error = ""
        for attempt in range(self.cfg["max_retries"] + 1):
            self._wait_for_slot()
            started = self.clock()
            request = urllib.request.Request(self.cfg["base_url"], data=body, headers=headers, method="POST")
            try:
                with self.opener(request, timeout=self.cfg["timeout_seconds"]) as response:
                    data = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:500]
                last_error = f"HTTP {exc.code}: {detail}"
                if exc.code == 429 and "per-day" in detail:
                    raise DailyLimitReached(last_error) from exc
                if exc.code in (401, 402, 403):
                    raise LLMError(last_error) from exc
                if exc.code not in (408, 429) and exc.code < 500:
                    raise LLMError(last_error) from exc
            except (OSError, http.client.HTTPException, json.JSONDecodeError) as exc:
                # Connection resets, timeouts and truncated bodies are transient; URLError is an OSError too.
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if "error" in data:
                    last_error = json.dumps(data["error"])[:500]
                elif data.get("choices"):
                    return {
                        "content": data["choices"][0]["message"].get("content") or "",
                        "model": data.get("model", self.model),
                        "usage": data.get("usage", {}),
                        "latency_s": round(self.clock() - started, 2),
                    }
                else:
                    last_error = "response without choices"
            self.sleep(min(60, 5 * 2 ** attempt))
        raise LLMError(f"gave up after {self.cfg['max_retries'] + 1} attempts: {last_error}")


def read_predictions() -> dict[tuple[str, str, str], dict]:
    return {(r["model"], r["prompt_version"], r["excerpt_sha"]): r for r in read_jsonl(PREDICTIONS)}


def classify_text(text: str, config: dict, client: OpenRouterClient, sample_id: str = "") -> dict:
    """Ask the model and store the answer. Returns the stored record."""
    cfg = config["llm"]
    reply = client.complete(build_messages(text, config["categories"], cfg["max_excerpt_chars"]))
    category, evidence, confidence = parse_response(reply["content"], config["categories"])
    usage = reply["usage"]
    record = {
        "sample_id": sample_id, "model": client.model, "served_by": reply["model"],
        "prompt_version": PROMPT_VERSION, "excerpt_sha": excerpt_sha(text),
        "category": category, "evidence": evidence, "confidence": confidence,
        "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
        "cost_usd": usage.get("cost", 0), "latency_s": reply["latency_s"],
        "raw": reply["content"][:2000], "at": now_iso(),
    }
    append_jsonl(PREDICTIONS, record)
    return record


def to_prediction(record: dict, abstain_below: float) -> tuple[str, str]:
    category = record["category"]
    confidence = record.get("confidence")
    if confidence is not None and confidence < abstain_below:
        category = UNKNOWN
    shown = f"{confidence:.2f}" if confidence is not None else "?"
    return category, f"conf={shown} | {record.get('evidence', '')}"


def cached_predictor(config: dict, model: str | None = None) -> Callable[[str], tuple[str, str] | None]:
    """Predictor for evaluate: answers from stored predictions only, None when a sample has no answer yet."""
    cfg = config["llm"]
    model = model or cfg["model"]
    stored = read_predictions()

    def predict(text: str) -> tuple[str, str] | None:
        record = stored.get((model, PROMPT_VERSION, excerpt_sha(text)))
        return None if record is None else to_prediction(record, cfg["abstain_below"])

    return predict


def main(argv: list[str] | None = None) -> None:
    config = load_config()
    cfg = config["llm"]
    parser = argparse.ArgumentParser(prog="python -m ci_classifier llm-run", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["test", "train"], default="test")
    parser.add_argument("--limit", type=int, default=None, help="maximum number of API calls this run")
    parser.add_argument("--model", default=cfg["model"])
    parser.add_argument("--source", choices=["github-actions", "logchunks"], help="only samples from this source")
    parser.add_argument("--reparse", action="store_true",
                        help="re-read category/evidence/confidence from the stored raw replies (no API calls)")
    args = parser.parse_args(argv)

    if args.reparse:
        records = read_jsonl(PREDICTIONS)
        changed = 0
        for record in records:
            parsed = parse_response(record.get("raw", ""), config["categories"])
            if parsed != (record["category"], record["evidence"], record["confidence"]):
                record["category"], record["evidence"], record["confidence"] = parsed
                changed += 1
        PREDICTIONS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        print(f"Re-parsed {len(records)} stored replies; {changed} changed.")
        return

    split = read_split()
    if split is None:
        parser.error("no data/split.json yet; run `python -m ci_classifier split` first")
    labels, manifest = read_labels(), read_manifest()
    # GitHub Actions samples are the target log format, so they get the scarce daily quota first.
    queue = sorted((sid for sid in split[args.split] if sid in labels
                    and (args.source is None or manifest[sid].get("source", "github-actions") == args.source)),
                   key=lambda sid: (manifest[sid].get("source", "github-actions") != "github-actions", sid))
    stored = read_predictions()
    missing = [sid for sid in queue if (args.model, PROMPT_VERSION, excerpt_sha(read_excerpt(sid))) not in stored]
    todo = missing if args.limit is None else missing[:args.limit]
    print(f"{len(queue) - len(missing)}/{len(queue)} {args.split} samples already answered by {args.model}; "
          f"calling the API for {len(todo)}.")

    client = OpenRouterClient(cfg, load_api_key(), args.model)
    done = 0
    for index, sid in enumerate(todo, start=1):
        try:
            record = classify_text(read_excerpt(sid), config, client, sid)
        except DailyLimitReached as exc:
            print(f"Daily free-model limit reached after {done} calls; run again tomorrow. ({exc})")
            break
        except LLMError as exc:
            print(f"  {index}/{len(todo)} {sid}: ERROR {exc}")
            if "HTTP 401" in str(exc) or "HTTP 402" in str(exc) or "HTTP 403" in str(exc):
                break
            continue
        done += 1
        mark = "=" if record["category"] == labels[sid]["label"] else "x"
        print(f"  {index}/{len(todo)} {mark} {sid}: {record['category']} (label {labels[sid]['label']}, "
              f"{record['latency_s']}s, {record['prompt_tokens']}+{record['completion_tokens']} tokens)")
    print(f"Stored {done} new answers in {PREDICTIONS.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
