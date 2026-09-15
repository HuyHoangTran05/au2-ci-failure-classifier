"""Cut each raw log down to the lines that explain why the run failed.

Usage:
    python -m ci_classifier excerpt          # only samples without an excerpt
    python -m ci_classifier excerpt --force  # rebuild all (after changing [excerpt] settings)

Set CI_EXCERPT_PROFILE=<name> to build a profile from [excerpt.profiles.<name>] into data/excerpts-<name>/;
every other command (evaluate, llm-run, classify...) reads the same variable.
"""

from __future__ import annotations

import argparse
import gzip
import re

from .common import excerpt_dir, excerpt_path, excerpt_profile, excerpt_settings, load_config, raw_path, read_manifest

ANSI = re.compile(r"(?:\x1b|\^\[)\[[0-9;?]*[A-Za-z]")
TIMESTAMP = re.compile(r"^\ufeff?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z ?")
# `gh run view --log-failed` lines: job<TAB>step<TAB>timestamp text. Other logs (e.g. Travis CI) may
# also contain tabs, so the timestamp is what identifies the format.
GH_LINE = re.compile(r"^[^\t]*\t[^\t]*\t\ufeff?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
TRAVIS_MARKER = re.compile(r"travis_(?:fold|time):\S*")
# Lines a CI system prints when a step fails: GitHub Actions, and Travis CI's failed-command message.
ERROR_MARKER = re.compile(r"##\[error\]|^The command \".*\" exited with [1-9]\d*\.")
# Lines worth keeping even when they are far from the final ##[error] marker.
KEY_LINE = re.compile(
    r"error (?:CS|TS|NU|MSB)\d{3,5}|error\[E\d{4}\]|: (?:fatal )?error:|npm ERR!|npm error"
    r"|Traceback \(most recent call last\)|\b\w+(?:Error|Exception):|Build FAILED|\bFAILED\b|--- FAIL:"
    r"|Unauthori[sz]ed|Forbidden|Bad credentials|No space left|rate limit|timed out",
)
# Words that often appear on lines describing a failure; used by the "hints" strategy to find candidate blocks.
ERROR_HINT = re.compile(
    r"(?i)\berrors?\b|\bfail(?:ed|ure|ures|ing|s)?\b|exception|traceback|assert|\bexpected\b|not found"
    r"|no such file|denied|forbidden|unauthori[sz]ed|\bcannot\b|can't|could not|couldn't|unable to|\bfatal\b"
    r"|\bpanic|segmentation fault|timed? ?out|refused|undefined|not defined|\bmissing\b|\binvalid\b|violation"
    r"|\baborted?\b|\bkilled\b|mismatch|\bconflict|dubious|✖|✗|ERR!"
)
STRATEGIES = ("marker", "hints")
UNKNOWN_JOB = "(unknown job)"
PLAIN_JOB = "log"


def clean_line(text: str) -> str:
    return TRAVIS_MARKER.sub("", ANSI.sub("", TIMESTAMP.sub("", text))).rstrip()


def is_gh_log(raw_text: str, probe: int = 20) -> bool:
    lines = [line for line in raw_text.splitlines()[:200] if line.strip()][:probe]
    return bool(lines) and 2 * sum(bool(GH_LINE.match(line)) for line in lines) > len(lines)


def parse_jobs(raw_text: str) -> dict[str, list[str]]:
    """Group log lines by job, keeping order.

    `gh run view --log-failed` output (job<TAB>step<TAB>line) is split per job; any other log is one job.
    """
    gh_format = is_gh_log(raw_text)
    jobs: dict[str, list[str]] = {}
    for line in raw_text.splitlines():
        if gh_format:
            parts = line.split("\t", 2)
            job, text = (parts[0], parts[2]) if len(parts) == 3 else (UNKNOWN_JOB, line)
        else:
            job, text = PLAIN_JOB, line
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
    markers = [i for i, text in enumerate(lines) if ERROR_MARKER.search(text)]
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


def hint_excerpt(lines: list[str], cfg: dict) -> list[str]:
    """Keep the highest-scoring blocks of failure-looking lines, up to `hint_budget` lines per job.

    Hint lines closer than `hint_gap` merge into one block. A block scores one point per hint line, extra points
    per KEY_LINE match, and a recency bonus (failures are usually reported near the end). The last error marker
    (or the log tail) is always kept, since it names the failing step.
    """
    width, budget = cfg["max_line_chars"], cfg["hint_budget"]
    gap, pad = cfg["hint_gap"], cfg["hint_padding"]
    n = len(lines)
    if n == 0:
        return ["-- context --"]

    blocks: list[list[int]] = []
    for i, text in enumerate(lines):
        if ERROR_HINT.search(text) and not ERROR_MARKER.search(text):
            if blocks and i - blocks[-1][-1] <= gap:
                blocks[-1].append(i)
            else:
                blocks.append([i])

    def score(block: list[int]) -> float:
        keys = sum(bool(KEY_LINE.search(lines[i])) for i in block)
        return len(block) + cfg["hint_key_weight"] * keys + cfg["hint_recency_weight"] * block[-1] / n

    markers = [i for i, text in enumerate(lines) if ERROR_MARKER.search(text)]
    anchor = markers[-1] if markers else n - 1
    keep: set[int] = set(range(max(0, anchor - cfg["hint_anchor_lines"] + 1), anchor + 1))
    for block in sorted(blocks, key=score, reverse=True):
        rows = range(max(0, block[0] - pad), min(n, block[-1] + pad + 1))
        if len(keep | set(rows)) > budget:
            continue
        keep.update(rows)

    out = ["-- context --"]
    previous = None
    for i in sorted(keep):
        if previous is not None and i != previous + 1:
            out.append("[...]")
        out.append(lines[i][:width])
        previous = i
    return out


def build_excerpt(raw_text: str, cfg: dict) -> str:
    jobs = parse_jobs(raw_text)
    select = hint_excerpt if cfg.get("strategy", "marker") == "hints" else job_excerpt
    out: list[str] = []
    omitted: list[str] = []
    for job, lines in jobs.items():
        section = [f"## job: {job}", *select(lines, cfg)]
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

    cfg = excerpt_settings(load_config())
    excerpt_dir().mkdir(parents=True, exist_ok=True)
    print(f"Excerpt profile: {excerpt_profile()} -> {excerpt_dir()}")
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
