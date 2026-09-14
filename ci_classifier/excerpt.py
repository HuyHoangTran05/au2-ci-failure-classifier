"""Cut each raw log down to the lines that explain why the run failed.

Usage:
    python -m ci_classifier excerpt          # only samples without an excerpt
    python -m ci_classifier excerpt --force  # rebuild all (after changing [excerpt] settings)
"""

from __future__ import annotations

import argparse
import gzip
import re

from .common import EXCERPT_DIR, excerpt_path, load_config, raw_path, read_manifest

ANSI = re.compile(r"(?:\x1b|\^\[)\[[0-9;?]*[A-Za-z]")
TIMESTAMP = re.compile(r"^\ufeff?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z ?")
ERROR_MARKER = "##[error]"
# Lines worth keeping even when they are far from the final ##[error] marker.
KEY_LINE = re.compile(
    r"error (?:CS|TS|NU|MSB)\d{3,5}|error\[E\d{4}\]|: (?:fatal )?error:|npm ERR!|npm error"
    r"|Traceback \(most recent call last\)|\b\w+(?:Error|Exception):|Build FAILED|\bFAILED\b|--- FAIL:"
    r"|Unauthori[sz]ed|Forbidden|Bad credentials|No space left|rate limit|timed out",
)
UNKNOWN_JOB = "(unknown job)"


def clean_line(text: str) -> str:
    return ANSI.sub("", TIMESTAMP.sub("", text)).rstrip()


def parse_jobs(raw_text: str) -> dict[str, list[str]]:
    """Group `gh run view --log-failed` output (job<TAB>step<TAB>line) by job, keeping order."""
    jobs: dict[str, list[str]] = {}
    for line in raw_text.splitlines():
        parts = line.split("\t", 2)
        job, text = (parts[0], parts[2]) if len(parts) == 3 else (UNKNOWN_JOB, line)
        text = clean_line(text)
        if text.startswith("##[endgroup]"):
            continue
        jobs.setdefault(job, []).append(text.replace("##[group]", ""))
    return jobs


def collapse_blank(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if line.strip() or (out and out[-1].strip()):
            out.append(line)
    return out


def job_excerpt(lines: list[str], cfg: dict) -> list[str]:
    width = cfg["max_line_chars"]
    markers = [i for i, text in enumerate(lines) if ERROR_MARKER in text]
    context_rows: set[int] = set()
    if markers:
        for i in markers[-3:]:
            context_rows.update(range(max(0, i - cfg["context_before_error"]), i + 1))
    else:
        context_rows.update(range(max(0, len(lines) - cfg["tail_lines_without_marker"]), len(lines)))

    key_lines: list[str] = []
    seen: set[str] = set()
    for i, text in enumerate(lines):
        stripped = text.strip()
        if i in context_rows or stripped in seen or not KEY_LINE.search(text):
            continue
        seen.add(stripped)
        key_lines.append(stripped[:width])
        if len(key_lines) >= cfg["max_key_lines"]:
            break

    out = ["-- key lines --", *key_lines] if key_lines else []
    context = collapse_blank([lines[i][:width] for i in sorted(context_rows)])
    budget = max(cfg["max_lines_per_job"] - len(out) - 1, 1)
    # The end of the context sits right before the error marker, so trim from the front.
    return [*out, "-- context --", *context[-budget:]]


def build_excerpt(raw_text: str, cfg: dict) -> str:
    jobs = parse_jobs(raw_text)
    out: list[str] = []
    omitted: list[str] = []
    for job, lines in jobs.items():
        section = [f"## job: {job}", *job_excerpt(lines, cfg)]
        if out and len(out) + len(section) > cfg["max_total_lines"]:
            omitted.append(job)
            continue
        out.extend(section)
    if omitted:
        out.append(f"## {len(omitted)} more failed jobs omitted: {', '.join(omitted)}")
    return "\n".join(out[: cfg["max_total_lines"] + 1]) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier excerpt", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="rebuild excerpts that already exist")
    args = parser.parse_args(argv)

    cfg = load_config()["excerpt"]
    EXCERPT_DIR.mkdir(parents=True, exist_ok=True)
    built = skipped = 0
    for sample_id, record in read_manifest().items():
        if record.get("status") != "ok" or not raw_path(sample_id).exists():
            continue
        target = excerpt_path(sample_id)
        if target.exists() and not args.force:
            skipped += 1
            continue
        raw_text = gzip.decompress(raw_path(sample_id).read_bytes()).decode("utf-8", "replace")
        target.write_text(build_excerpt(raw_text, cfg), encoding="utf-8")
        built += 1
    print(f"Done: {built} excerpts built, {skipped} already present.")


if __name__ == "__main__":
    main()
