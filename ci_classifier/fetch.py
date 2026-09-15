"""Download logs of failed GitHub Actions runs from public repositories.

Usage:
    python -m ci_classifier fetch
    python -m ci_classifier fetch --repo python/cpython --runs-per-repo 5

Already downloaded runs are skipped, so the command can be re-run after an interruption.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
import time
from collections import Counter

from .common import (RAW_DIR, append_manifest, excerpt_settings, load_config, now_iso, raw_path, read_manifest,
                     sample_id_for)
from .excerpt import build_excerpt

RUN_FIELDS = "databaseId,workflowName,event,headBranch,headSha,createdAt,url,displayTitle"
# GitHub deletes logs after the retention period; retrying these never helps.
PERMANENT_ERRORS = ("log not found", "HTTP 410")


def gh(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, timeout=timeout)


def list_failed_runs(repo: str, scan_limit: int, timeout: int) -> list[dict]:
    result = gh(
        ["run", "list", "-R", repo, "--status", "failure", "--limit", str(scan_limit), "--json", RUN_FIELDS],
        timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return json.loads(result.stdout)


def select_runs(runs: list[dict], runs_per_repo: int, max_per_workflow: int) -> list[dict]:
    """Keep the newest runs while capping how many come from any single workflow."""
    per_workflow: Counter[str] = Counter()
    chosen = []
    for run in runs:
        if per_workflow[run["workflowName"]] >= max_per_workflow:
            continue
        per_workflow[run["workflowName"]] += 1
        chosen.append(run)
        if len(chosen) >= runs_per_repo:
            break
    return chosen


def is_permanent(error: str) -> bool:
    return any(marker in error for marker in PERMANENT_ERRORS)


def download_log(repo: str, run_id: int, timeout: int, attempts: int = 3) -> tuple[bytes | None, str]:
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            result = gh(["run", "view", str(run_id), "-R", repo, "--log-failed"], timeout)
        except subprocess.TimeoutExpired:
            last_error = f"timeout after {timeout}s"
        else:
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout, ""
            last_error = result.stderr.decode("utf-8", "replace").strip() or "empty log"
            if is_permanent(last_error):
                break
        if attempt < attempts:
            time.sleep(2 * attempt)
    return None, last_error


def main(argv: list[str] | None = None) -> None:
    full_config = load_config()
    config = full_config["fetch"]
    parser = argparse.ArgumentParser(prog="python -m ci_classifier fetch", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", action="append", help="owner/name; may be repeated (default: config.toml)")
    parser.add_argument("--runs-per-repo", type=int, default=config["runs_per_repo"])
    parser.add_argument("--max-per-workflow", type=int, default=config["max_per_workflow"])
    parser.add_argument("--workflow-filter", metavar="REGEX",
                        help="only consider workflows whose name matches (case-insensitive)")
    parser.add_argument("--require", metavar="REGEX",
                        help="keep a log only if its excerpt matches; others are recorded as filtered_out")
    parser.add_argument("--tag", default="sample",
                        help="stored as `retrieval` in the manifest, so targeted samples can be reported apart")
    args = parser.parse_args(argv)

    workflow_filter = re.compile(args.workflow_filter, re.IGNORECASE) if args.workflow_filter else None
    require = re.compile(args.require) if args.require else None
    timeout = config["timeout_seconds"]
    manifest = read_manifest()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    totals: Counter[str] = Counter()

    for repo in args.repo or config["repos"]:
        try:
            runs = list_failed_runs(repo, config["scan_limit"], timeout)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"[{repo}] cannot list runs: {exc}")
            totals["repo_errors"] += 1
            continue

        if workflow_filter:
            runs = [run for run in runs if workflow_filter.search(run["workflowName"])]
        selected = select_runs(runs, args.runs_per_repo, args.max_per_workflow)
        print(f"[{repo}] {len(runs)} failed runs considered, {len(selected)} selected")

        for index, run in enumerate(selected, start=1):
            sample_id = sample_id_for(repo, run["databaseId"])
            previous = manifest.get(sample_id, {})
            if (previous.get("status") == "ok" and raw_path(sample_id).exists()) or is_permanent(
                previous.get("error", "")
            ) or previous.get("status") == "filtered_out":
                totals["skipped"] += 1
                continue

            log, error = download_log(repo, run["databaseId"], timeout)
            record = {
                "sample_id": sample_id,
                "source": "github-actions",
                "repo": repo,
                "run_id": run["databaseId"],
                "workflow": run["workflowName"],
                "event": run["event"],
                "head_branch": run["headBranch"],
                "head_sha": run["headSha"],
                "created_at": run["createdAt"],
                "url": run["url"],
                "title": run["displayTitle"],
                "retrieval": args.tag,
                "fetched_at": now_iso(),
            }
            if log is None:
                record.update(status="error", error=error)
                totals["errors"] += 1
                print(f"  {index}/{len(selected)} {sample_id}: ERROR {error[:120]}")
            elif require and not require.search(build_excerpt(log.decode("utf-8", "replace"),
                                                              excerpt_settings(full_config))):
                # Only the verdict is kept, so the run is not downloaded again next time.
                record.update(status="filtered_out", raw_bytes=len(log))
                totals["filtered_out"] += 1
                print(f"  {index}/{len(selected)} {sample_id}: no match, not kept")
            else:
                raw_path(sample_id).write_bytes(gzip.compress(log))
                record.update(status="ok", raw_bytes=len(log))
                totals["downloaded"] += 1
                print(f"  {index}/{len(selected)} {sample_id}: {len(log) / 1_000_000:.1f} MB")
            append_manifest(record)
            manifest[sample_id] = record

    print(
        f"Done: {totals['downloaded']} downloaded, {totals['skipped']} skipped (already present or log expired), "
        f"{totals['errors']} failed downloads, {totals['filtered_out']} not matching --require, "
        f"{totals['repo_errors']} repos unavailable."
    )


if __name__ == "__main__":
    main()
