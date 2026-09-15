"""A panel of LLMs from different model families relabels the blind-round test samples; people review disputes.

The panel never sees the existing label, its note or any classifier prediction. Each model gets what a human
labeller gets in `label --blind`: repo, workflow, title, the LogChunks marked chunk (when there is one) and the
excerpt, with the rules from docs/labeling-guide.md. Answers go to data/panel_labels.jsonl, keyed by
(model, prompt version, input hash); data/labels.jsonl is never changed here.

Panel labels are not ground truth: models share training data and can share mistakes. They are used to find the
samples a person should read (`label --adjudicate --panel`) and to measure how ambiguous the labels are.

Usage:
    python -m ci_classifier panel-run                       # every configured model on the 80 blind-round samples
    python -m ci_classifier panel-run --model cohere/north-mini-code:free --limit 10
    python -m ci_classifier panel-report                    # agreement, Fleiss' kappa, review queue
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime

import numpy as np
import pandas as pd

from . import agreement, llm
from .common import (DATA, RESULTS, UNKNOWN, append_jsonl, load_config, now_iso, read_excerpt, read_jsonl, read_labels,
                     read_manifest, read_split)
from .split import group_of

PANEL_LABELS = DATA / "panel_labels.jsonl"
PANEL_PROMPT_VERSION = "panel-v1"

PANEL_SYSTEM_PROMPT = """You label failed CI jobs for a research data set. Decide why the job failed, using exactly one category.

Categories:
- compilation: the code does not compile or type-check (compiler or type-checker errors, syntax errors, linker errors)
- test_assertion: the code builds but tests give wrong results (assertion failures, failing test cases, snapshot
  mismatch, a single test timing out)
- dependency: packages or libraries cannot be installed, downloaded or resolved (registry errors, version conflicts,
  missing modules, install scripts of a package failing)
- authentication: missing or wrong credentials, tokens, secrets or permissions (401/403 from an auth check,
  Bad credentials)
- infrastructure: the CI machine or network fails, not the code (runner lost, disk full, the whole job cancelled for
  running too long, connection resets, DNS, 5xx from external services, quota or rate limits)
- other: a clear cause outside the categories above (lint or format checks, docs build, link checkers, PR label or
  policy checks, generated files not committed, bugs in the workflow's own scripts)
- unknown: the log does not contain enough evidence to decide

Rules:
1. Pick the root cause, not a consequence: a missing package that breaks the build is dependency, not compilation.
2. Ignore summary jobs that only report that other jobs failed; look at the job that really failed.
3. If several jobs fail for different reasons, pick the cause of the most important build or test job.
4. A test that fails because a network or external service is down: infrastructure if the environment is at fault,
   not the logic under test; if unsure, test_assertion.
5. One specific test running too long is test_assertion; the whole job cancelled for exceeding its time is
   infrastructure.
6. If the log is not enough to decide, answer unknown. Do not guess.
7. When a "marked failure chunk" is given, it shows where the failure is, not which category it belongs to.

Reply with only a JSON object, no other text:
{"category": "<one category name or unknown>", "evidence": "<the single log line that shows the cause, copied verbatim>", "confidence": <number from 0 to 1>}"""


def build_panel_messages(record: dict, excerpt: str, max_chars: int) -> list[dict]:
    if len(excerpt) > max_chars:
        excerpt = "[... earlier lines omitted ...]\n" + excerpt[-max_chars:]
    parts = [f"repo: {record.get('repo', '')}", f"workflow: {record.get('workflow', '')}",
             f"title: {record.get('title', '')}"]
    if record.get("chunk"):
        parts.append("Marked failure chunk (LogChunks authors marked these lines as the failure):\n```\n"
                     f"{record['chunk'].rstrip()}\n```")
    parts.append(f"Log excerpt:\n```\n{excerpt.rstrip()}\n```")
    return [{"role": "system", "content": PANEL_SYSTEM_PROMPT}, {"role": "user", "content": "\n\n".join(parts)}]


def input_sha(messages: list[dict]) -> str:
    return hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def read_panel() -> dict[tuple[str, str, str], dict]:
    return {(r["model"], r["prompt_version"], r["input_sha"]): r for r in read_jsonl(PANEL_LABELS)}


def panel_samples(config: dict, count: int | None = None) -> list[str]:
    """The same fixed sample as `label --blind`, so panel and human rounds can be compared."""
    manifest, labels, split = read_manifest(), read_labels(), read_split()
    if split is None:
        raise SystemExit("no data/split.json yet; run `python -m ci_classifier split` first")
    test_ids = [sid for sid in split["test"] if sid in labels]
    return agreement.blind_queue(test_ids, manifest, set(), count or config["panel"]["sample_count"],
                                 config["split"]["seed"])


def votes_for(sample_ids: list[str], models: list[str], config: dict) -> dict[str, dict[str, str]]:
    """sample -> {model: category} for stored answers matching the current prompt and inputs."""
    manifest, stored = read_manifest(), read_panel()
    max_chars = config["llm"]["max_excerpt_chars"]
    votes: dict[str, dict[str, str]] = {}
    for sid in sample_ids:
        sha = input_sha(build_panel_messages(manifest[sid], read_excerpt(sid), max_chars))
        votes[sid] = {m: stored[(m, PANEL_PROMPT_VERSION, sha)]["category"]
                      for m in models if (m, PANEL_PROMPT_VERSION, sha) in stored}
    return votes


def decide(votes: dict[str, str], draft: str, models: list[str]) -> tuple[str, str | None]:
    """(bucket, majority label). A majority needs more than half of the configured models on one real category."""
    counts = Counter(v for v in votes.values() if v != UNKNOWN)
    top, n = counts.most_common(1)[0] if counts else (None, 0)
    majority = top if n > len(models) / 2 else None
    if len(votes) < len(models):
        return "incomplete", majority
    if majority is None:
        return "split", None
    return ("confirmed" if majority == draft else "contested"), majority


def fleiss_kappa(ratings: list[list[str]], categories: list[str]) -> float:
    """Fleiss' kappa for items rated by the same number of raters (each item: one label per rater)."""
    if not ratings:
        return math.nan
    raters = len(ratings[0])
    table = np.array([[row.count(c) for c in categories] for row in ratings], dtype=float)
    p_items = ((table * (table - 1)).sum(axis=1)) / (raters * (raters - 1))
    p_bar = p_items.mean()
    p_cat = table.sum(axis=0) / (len(ratings) * raters)
    p_e = float((p_cat ** 2).sum())
    return 1.0 if p_e == 1 else float((p_bar - p_e) / (1 - p_e))


def review_items(config: dict) -> list[tuple[str, list[str], str]]:
    """(sample, candidate labels, note) for contested and split samples, for `label --adjudicate --panel`."""
    models = config["panel"]["models"]
    drafts = agreement.original_drafts()
    items = []
    for sid, votes in votes_for(panel_samples(config), models, config).items():
        bucket, _ = decide(votes, drafts[sid], models)
        if bucket not in ("contested", "split"):
            continue
        candidates = sorted({drafts[sid], *(v for v in votes.values() if v != UNKNOWN)})
        shown = ", ".join(f"{m.split('/')[0]}={v}" for m, v in votes.items())
        items.append((sid, candidates, f"panel {bucket}: draft={drafts[sid]}; {shown}"))
    return items


def run(argv: list[str] | None = None) -> None:
    config = load_config()
    parser = argparse.ArgumentParser(prog="python -m ci_classifier panel-run", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", action="append", help="only this model (repeatable); default: [panel] models")
    parser.add_argument("--limit", type=int, default=None, help="maximum API calls per model this run")
    parser.add_argument("--count", type=int, default=None, help="sample size (default [panel] sample_count)")
    args = parser.parse_args(argv)

    panel_cfg, llm_cfg = config["panel"], config["llm"]
    models = args.model or panel_cfg["models"]
    client_cfg = {**llm_cfg, "max_tokens": panel_cfg["max_tokens"], "requests_per_minute": panel_cfg["requests_per_minute"]}
    key = llm.load_api_key()
    clients = {m: llm.OpenRouterClient(client_cfg, key, m) for m in models}
    manifest, stored = read_manifest(), read_panel()
    samples = panel_samples(config, args.count)
    calls = Counter()
    active = list(models)
    print(f"Panel {PANEL_PROMPT_VERSION}: {len(models)} models x {len(samples)} samples. Labels and predictions are hidden.")

    # Sample by sample, so a stopped run still leaves complete votes for the samples it reached.
    for index, sid in enumerate(samples, start=1):
        messages = build_panel_messages(manifest[sid], read_excerpt(sid), llm_cfg["max_excerpt_chars"])
        sha = input_sha(messages)
        for model in list(active):
            if (model, PANEL_PROMPT_VERSION, sha) in stored or (args.limit is not None and calls[model] >= args.limit):
                continue
            try:
                reply = clients[model].complete(messages)
            except llm.DailyLimitReached as exc:
                print(f"  {model}: daily limit reached, skipping it for this run ({str(exc)[:80]})")
                active.remove(model)
                continue
            except llm.LLMError as exc:
                print(f"  {index}/{len(samples)} {sid} {model}: ERROR {str(exc)[:160]}")
                if any(code in str(exc) for code in ("HTTP 401", "HTTP 402", "HTTP 403")):
                    active.remove(model)
                continue
            category, evidence, confidence = llm.parse_response(reply["content"], config["categories"])
            usage = reply["usage"]
            record = {
                "sample_id": sid, "model": model, "served_by": reply["model"], "prompt_version": PANEL_PROMPT_VERSION,
                "input_sha": sha, "category": category, "evidence": evidence, "confidence": confidence,
                "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                "cost_usd": usage.get("cost", 0), "latency_s": reply["latency_s"], "raw": reply["content"][:2000],
                "at": now_iso(),
            }
            append_jsonl(PANEL_LABELS, record)
            stored[(model, PANEL_PROMPT_VERSION, sha)] = record
            calls[model] += 1
            # Deliberately no comparison with the label here: the operator should not see labels either.
            print(f"  {index}/{len(samples)} {sid} {model.split('/')[0]}: answered ({reply['latency_s']}s)")
        if not active:
            break
    done = votes_for(samples, models, config)
    complete = sum(len(v) == len(models) for v in done.values())
    print(f"Stored {sum(calls.values())} new answers. Samples with all {len(models)} votes: {complete}/{len(samples)}.")


def report(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier panel-report", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)
    config = load_config()
    categories, models = config["categories"], config["panel"]["models"]
    manifest, labels = read_manifest(), read_labels()
    drafts = agreement.original_drafts()
    samples = panel_samples(config)
    votes = votes_for(samples, models, config)
    boot, seed = config["evaluation"]["bootstrap_samples"], config["split"]["seed"]

    per_model = []
    for model in models:
        ids = [sid for sid in samples if votes[sid].get(model, UNKNOWN) != UNKNOWN]
        answered = sum(model in votes[sid] for sid in samples)
        row = {"model": model, "answered": answered, "unknown": answered - len(ids)}
        if ids:
            row.update(agreement.compare([drafts[s] for s in ids], [votes[s][model] for s in ids],
                                         [group_of(manifest[s]) for s in ids], categories, boot, seed))
        per_model.append(row)

    full = [sid for sid in samples if len(votes[sid]) == len(models)
            and all(v != UNKNOWN for v in votes[sid].values())]
    fleiss = fleiss_kappa([[votes[s][m] for m in models] for s in full], categories)

    rows = []
    for sid in samples:
        bucket, majority = decide(votes[sid], drafts[sid], models)
        rows.append({"sample_id": sid, "source": manifest[sid].get("source", "github-actions"), "bucket": bucket,
                     "draft": drafts[sid], "majority": majority or "",
                     **{m.split("/")[0]: votes[sid].get(m, "") for m in models},
                     "current": labels[sid]["label"],
                     "adjudicated": labels[sid].get("note", "").startswith(agreement.ADJUDICATED)})
    table = pd.DataFrame(rows)
    buckets = table["bucket"].value_counts().to_dict()
    with_majority = table[table["majority"] != ""]
    majority_agreement = (with_majority["majority"] == with_majority["draft"]).mean() if len(with_majority) else math.nan

    out_dir = RESULTS / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-panel")
    out_dir.mkdir(parents=True)
    table.to_csv(out_dir / "votes.csv", index=False)
    table.loc[table["bucket"].isin(["contested", "split"]), ["sample_id", "source", "bucket"]].to_csv(
        out_dir / "review_queue.csv", index=False)
    summary = {"created_at": now_iso(), "prompt_version": PANEL_PROMPT_VERSION, "models": models,
               "samples": len(samples), "buckets": buckets, "majority_agreement_with_draft": majority_agreement,
               "fleiss_kappa_all_answered": fleiss, "fleiss_samples": len(full), "per_model": per_model}
    (out_dir / "panel.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")

    print(f"Panel {PANEL_PROMPT_VERSION} on {len(samples)} samples; buckets: {buckets}")
    for row in per_model:
        if "kappa" in row:
            print(f"  {row['model']:40} answered={row['answered']:3} unknown={row['unknown']:2} "
                  f"agreement={row['agreement']:.2f} kappa={row['kappa']:.2f} [{row['kappa_low']:.2f}, {row['kappa_high']:.2f}]")
        else:
            print(f"  {row['model']:40} answered={row['answered']:3} (no usable answers yet)")
    print(f"Majority label equals draft on {majority_agreement:.2f} of {len(with_majority)} samples with a majority")
    print(f"Fleiss' kappa among the panel: {fleiss:.2f} on {len(full)} samples all models labelled")
    print(f"Review queue: {buckets.get('contested', 0) + buckets.get('split', 0)} samples -> {out_dir / 'review_queue.csv'}")
    print("Settle them with `python -m ci_classifier label --adjudicate --panel --labeler <name>`.")
    print(f"votes.csv shows draft labels: open it only after adjudicating. Summary: {out_dir / 'panel.json'}")
    if buckets.get("incomplete"):
        print(f"{buckets['incomplete']} samples still lack a vote; run panel-run again.")


if __name__ == "__main__":
    run()
