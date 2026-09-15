"""Download a successful "baseline" run for each failed GitHub Actions sample.

For a failed run, the baseline is the most recent successful run of the same workflow created before it,
preferring the same branch and falling back to any branch. Only the jobs that failed in the sample are
downloaded, by name. The `baseline-diff` excerpt strategy then drops failed-job lines whose template also
appears in the baseline job, leaving the lines that are new in the failing run.

Usage:
    python -m ci_classifier fetch-baselines
    python -m ci_classifier fetch-baselines --labelled-only --workers 4

Output: data/baselines/<sample_id>.json.gz (job name -> log text), data/baselines.jsonl (one record per sample)
"""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from .common import DATA, append_jsonl, load_config, now_iso, read_jsonl, read_labels, read_manifest

BASELINE_DIR = DATA / "baselines"
BASELINE_INDEX = DATA / "baselines.jsonl"


def gh_json(args: list[str], timeout: int) -> dict | list:
    result = subprocess.run(["gh", *args], capture_output=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip()[:300])
    return json.loads(result.stdout)


def gh_text(args: list[str], timeout: int) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip()[:300])
    return result.stdout.decode("utf-8", "replace")


def baseline_path(sample_id: str):
    return BASELINE_DIR / f"{sample_id}.json.gz"


def read_baseline(sample_id: str) -> dict[str, list[str]] | None:
    """Job name -> baseline log lines, or None when the sample has no baseline."""
    path = baseline_path(sample_id)
    if not path.exists():
        return None
    jobs = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))["jobs"]
    return {name: text.splitlines() for name, text in jobs.items()}


def find_baseline_run(repo: str, workflow_id: int, branch: str, before: str, timeout: int) -> dict | None:
    for branch_filter in (branch, None):
        query = {"status": "success", "per_page": "5", "created": f"<{before}"}
        if branch_filter:
            query["branch"] = branch_filter
        url = f"repos/{repo}/actions/workflows/{workflow_id}/runs?{urllib.parse.urlencode(query)}"
        runs = gh_json(["api", url], timeout)["workflow_runs"]
        if runs:
            run = runs[0]
            return {"baseline_run_id": run["id"], "branch": run["head_branch"], "same_branch": branch_filter is not None,
                    "created_at": run["created_at"]}
    return None


def fetch_one(record: dict, timeout: int) -> dict:
    repo, run_id = record["repo"], record["run_id"]
    info = gh_json(["run", "view", str(run_id), "-R", repo, "--json", "workflowDatabaseId,headBranch,createdAt,jobs"],
                   timeout)
    failed_jobs = [job["name"] for job in info["jobs"] if job["conclusion"] == "failure"]
    baseline = find_baseline_run(repo, info["workflowDatabaseId"], info["headBranch"], info["createdAt"], timeout)
    if baseline is None:
        return {"status": "no_success_run", "failed_jobs": len(failed_jobs)}

    by_name = {job["name"]: job for job in list_jobs(repo, baseline["baseline_run_id"], timeout)
               if job["conclusion"] == "success"}
    logs = {}
    for name in failed_jobs:
        job = by_name.get(name)
        if job is None:
            continue
        try:
            logs[name] = gh_text(["api", f"repos/{repo}/actions/jobs/{job['id']}/logs"], timeout)
        except RuntimeError:
            continue
    if not logs:
        return {"status": "no_matching_job", "failed_jobs": len(failed_jobs), **baseline}
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"success_run_id": baseline["baseline_run_id"], "jobs": logs}
    baseline_path(record["sample_id"]).write_bytes(gzip.compress(json.dumps(payload).encode("utf-8")))
    return {"status": "ok", "failed_jobs": len(failed_jobs), "matched_jobs": len(logs),
            "baseline_bytes": sum(len(text) for text in logs.values()), **baseline}


def list_jobs(repo: str, run_id: int, timeout: int) -> list[dict]:
    text = gh_text(["api", "--paginate", f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100",
                    "--jq", ".jobs[] | {name, id, conclusion}"], timeout)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> None:
    config = load_config()
    parser = argparse.ArgumentParser(prog="python -m ci_classifier fetch-baselines", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, help="maximum number of samples to process this run")
    parser.add_argument("--labelled-only", action="store_true", help="skip samples without a label")
    parser.add_argument("--workers", type=int, default=4, help="samples fetched in parallel")
    args = parser.parse_args(argv)

    timeout = config["fetch"]["timeout_seconds"]
    done = {r["sample_id"] for r in read_jsonl(BASELINE_INDEX)}
    labels = read_labels()
    todo = [r for r in read_manifest().values()
            if r.get("source", "github-actions") == "github-actions" and r.get("status") == "ok"
            and r["sample_id"] not in done and (not args.labelled_only or r["sample_id"] in labels)]
    if args.limit is not None:
        todo = todo[:args.limit]
    print(f"{len(done)} samples already processed; fetching baselines for {len(todo)}.", flush=True)

    def work(record: dict) -> tuple[dict, dict]:
        try:
            return record, fetch_one(record, timeout)
        except (RuntimeError, subprocess.TimeoutExpired, KeyError, json.JSONDecodeError) as exc:
            return record, {"status": "error", "error": str(exc)[:300]}

    totals: Counter[str] = Counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        # Only the main thread appends to the index, so records never interleave.
        for index, (record, result) in enumerate(pool.map(work, todo), start=1):
            append_jsonl(BASELINE_INDEX, {"sample_id": record["sample_id"], **result, "fetched_at": now_iso()})
            totals[result["status"]] += 1
            jobs = f" ({result.get('matched_jobs')}/{result.get('failed_jobs')} jobs)" if result["status"] == "ok" else ""
            print(f"  {index}/{len(todo)} {record['sample_id']}: {result['status']}{jobs}", flush=True)
    print("Done: " + ", ".join(f"{k}={v}" for k, v in totals.items()))


if __name__ == "__main__":
    main()
