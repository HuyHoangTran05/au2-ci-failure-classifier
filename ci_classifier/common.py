"""Shared paths, configuration and small file helpers."""

from __future__ import annotations

import json
import os
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_DIR = DATA / "raw"
EXCERPT_DIR = DATA / "excerpts"
MANIFEST = DATA / "manifest.jsonl"
LABELS = DATA / "labels.jsonl"
SPLIT = DATA / "split.json"
TRIAGE_LOG = DATA / "triage_sessions.jsonl"
BLIND_LABELS = DATA / "blind_labels.jsonl"
RESULTS = ROOT / "results"

UNKNOWN = "unknown"


def load_config(path: Path = ROOT / "config.toml") -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def runbook_for(category: str, config: dict) -> str:
    return config.get("runbooks", {}).get(category, "")


def sample_id_for(repo: str, run_id: int) -> str:
    owner, name = repo.split("/", 1)
    return f"{owner}__{name}__{run_id}"


def raw_path(sample_id: str) -> Path:
    return RAW_DIR / f"{sample_id}.log.gz"


DEFAULT_PROFILE = "default"


def excerpt_profile() -> str:
    """Active excerpt profile, chosen with the CI_EXCERPT_PROFILE environment variable."""
    return os.environ.get("CI_EXCERPT_PROFILE", DEFAULT_PROFILE).strip() or DEFAULT_PROFILE


def excerpt_settings(config: dict, profile: str | None = None) -> dict:
    """[excerpt] settings with the named profile's overrides ([excerpt.profiles.<name>]) applied."""
    profile = profile or excerpt_profile()
    settings = {k: v for k, v in config["excerpt"].items() if k != "profiles"}
    if profile != DEFAULT_PROFILE:
        profiles = config["excerpt"].get("profiles", {})
        if profile not in profiles:
            raise SystemExit(f"Unknown excerpt profile {profile!r}; defined: {', '.join(profiles) or 'none'}")
        settings.update(profiles[profile])
    return settings


def excerpt_dir(profile: str | None = None) -> Path:
    """Each profile keeps its own excerpts, so profiles can be compared without overwriting each other."""
    profile = profile or excerpt_profile()
    return EXCERPT_DIR if profile == DEFAULT_PROFILE else DATA / f"excerpts-{profile}"


def excerpt_path(sample_id: str) -> Path:
    return excerpt_dir() / f"{sample_id}.txt"


def read_excerpt(sample_id: str) -> str:
    return excerpt_path(sample_id).read_text(encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    """Records of a JSONL file. A last line cut off mid-write (no newline, not valid JSON) is skipped with a warning;
    an invalid line anywhere else still raises, since that is real corruption."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    records = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            if index == len(lines) - 1 and not text.endswith("\n"):
                print(f"Warning: ignoring an incomplete last line in {path.name} (interrupted write)", file=sys.stderr)
                continue
            raise
    return records


def repair_partial_tail(path: Path) -> int:
    """Drop bytes after the last newline: a record without its newline was never completely written.

    Returns the number of bytes removed. Called before appending, so a new record never glues onto a broken one.
    """
    if not path.exists():
        return 0
    with path.open("rb+") as f:
        size = f.seek(0, os.SEEK_END)
        if size == 0:
            return 0
        f.seek(-1, os.SEEK_END)
        if f.read(1) == b"\n":
            return 0
        # Scan back in blocks for the last complete line.
        position, block = size, 1 << 16
        while position > 0:
            start = max(0, position - block)
            f.seek(start)
            chunk = f.read(position - start)
            cut = chunk.rfind(b"\n")
            if cut != -1:
                keep = start + cut + 1
                break
            position = start
        else:
            keep = 0
        f.truncate(keep)
    print(f"Warning: removed an incomplete last record ({size - keep} bytes) from {path.name}", file=sys.stderr)
    return size - keep


def append_jsonl(path: Path, record: dict) -> None:
    """Append one record and force it to disk, so a crash or power cut loses at most the record being written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    repair_partial_tail(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_manifest() -> dict[str, dict]:
    """Return manifest records by sample id; a later line replaces an earlier one (retries)."""
    return {record["sample_id"]: record for record in read_jsonl(MANIFEST)}


def append_manifest(record: dict) -> None:
    append_jsonl(MANIFEST, record)


def read_labels() -> dict[str, dict]:
    """Return labels by sample id; a later line replaces an earlier one (relabels)."""
    return {record["sample_id"]: record for record in read_jsonl(LABELS)}


HUMAN = "human"
DRAFT_LABELER = "claude-draft"


def append_label(sample_id: str, label: str, note: str = "", labeler: str = HUMAN) -> None:
    """Record a label. `labeler` tells human labels apart from unreviewed drafts."""
    append_jsonl(LABELS, {"sample_id": sample_id, "label": label, "note": note, "labeler": labeler,
                          "labeled_at": now_iso()})


def read_split() -> dict | None:
    if not SPLIT.exists():
        return None
    return json.loads(SPLIT.read_text(encoding="utf-8"))
