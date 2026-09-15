"""Import the LogChunks data set (797 Travis CI failure logs, CC BY 4.0) as extra samples.

Each LogChunks example has a human-marked chunk explaining why the build failed. The chunk is stored in
the manifest and shown by `label` as a hint, so labelling takes seconds instead of reading the whole log.
Classifiers never see the chunk: they get an excerpt built from the raw log, exactly like any other sample.

Source: Brandt, Panichella, Zaidman, Beller. "LogChunks: A Data Set for Build Log Analysis", MSR 2020.
https://doi.org/10.5281/zenodo.3632351

Usage:
    python -m ci_classifier import-logchunks
    python -m ci_classifier import-logchunks --zip path/to/LogChunks.zip
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import re
import shutil
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .common import (DATA, RAW_DIR, append_manifest, excerpt_dir, excerpt_path, excerpt_settings, load_config, now_iso,
                     raw_path, read_manifest)
from .excerpt import build_excerpt, clean_line

SOURCE = "logchunks"
RECORD_URL = "https://zenodo.org/records/3632351"
ZIP_URL = "https://zenodo.org/api/records/3632351/files/LogChunks.zip/content"
ZIP_MD5 = "aafa45079bdae44e340f4474ca5c4340"
DEFAULT_ZIP = DATA / "external" / "LogChunks.zip"


def md5_of(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    print(f"Downloading {ZIP_URL} ...")
    with urllib.request.urlopen(ZIP_URL, timeout=120) as response, partial.open("wb") as f:
        shutil.copyfileobj(response, f)
    partial.replace(target)


def iter_examples(archive: zipfile.ZipFile):
    """Yield dicts with language, repo, job id, log bytes, chunk and keywords."""
    for name in sorted(archive.namelist()):
        match = re.match(r"LogChunks/build-failure-reason/(?P<language>[^/]+)/[^/]+\.xml$", name)
        if not match:
            continue
        for example in ET.fromstring(archive.read(name)):
            log_rel = example.findtext("Log")  # e.g. C/git@git/failed/564416725.log
            _, repo_dir, _, file_name = log_rel.split("/")
            owner, _, repo_name = repo_dir.partition("@")
            yield {
                "language": match["language"],
                "repo": f"{owner}/{repo_name}",
                "job_id": Path(file_name).stem,
                "log_path": log_rel,
                "log": archive.read(f"LogChunks/logs/{log_rel}"),
                "chunk": example.findtext("Chunk") or "",
                "keywords": [k.strip() for k in (example.findtext("Keywords") or "").split(",") if k.strip()],
            }


# LogChunks chunk text lost the ESC byte of colour codes ("[31m") and every "<" character ("Promisevoid>"),
# so both sides of the comparison drop them; otherwise identical lines fail to match.
BARE_ANSI = re.compile(r"\[[0-9;]*[mK]")


def normalize_line(line: str) -> str:
    return " ".join(BARE_ANSI.sub("", clean_line(line)).replace("<", "").split())


def chunk_coverage(chunk: str, excerpt: str) -> float:
    """Share of the chunk's non-empty lines that also appear (as a substring of a line) in the excerpt."""
    chunk_lines = {normalize_line(line) for line in chunk.splitlines()} - {""}
    if not chunk_lines:
        return 1.0
    excerpt_text = "\n".join(normalize_line(line) for line in excerpt.splitlines())
    return sum(line in excerpt_text for line in chunk_lines) / len(chunk_lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ci_classifier import-logchunks", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP, help="LogChunks.zip (downloaded if missing)")
    args = parser.parse_args(argv)

    if not args.zip.exists():
        download(args.zip)
    actual_md5 = md5_of(args.zip)
    if actual_md5 != ZIP_MD5:
        raise SystemExit(f"Checksum mismatch for {args.zip}: {actual_md5} != {ZIP_MD5}. Delete it and retry.")

    cfg = excerpt_settings(load_config())
    manifest = read_manifest()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    excerpt_dir().mkdir(parents=True, exist_ok=True)
    imported = skipped = 0
    coverage: list[float] = []

    with zipfile.ZipFile(args.zip) as archive:
        for example in iter_examples(archive):
            owner, name = example["repo"].split("/")
            sample_id = f"{SOURCE}__{owner}__{name}__{example['job_id']}"
            if sample_id in manifest and raw_path(sample_id).exists():
                skipped += 1
                continue
            raw_path(sample_id).write_bytes(gzip.compress(example["log"]))
            excerpt = build_excerpt(example["log"].decode("utf-8", "replace"), cfg)
            excerpt_path(sample_id).write_text(excerpt, encoding="utf-8")
            coverage.append(chunk_coverage(example["chunk"], excerpt))
            append_manifest({
                "sample_id": sample_id,
                "source": SOURCE,
                "repo": example["repo"],
                "run_id": example["job_id"],
                "workflow": "travis-ci",
                "event": "",
                "language": example["language"],
                "title": example["log_path"],
                "url": RECORD_URL,
                "chunk": example["chunk"],
                "keywords": example["keywords"],
                "status": "ok",
                "raw_bytes": len(example["log"]),
                "fetched_at": now_iso(),
            })
            imported += 1

    print(f"Done: {imported} imported, {skipped} already present.")
    if coverage:
        full = sum(c == 1.0 for c in coverage)
        print(f"Excerpt quality: the human-marked chunk is fully inside the excerpt for {full}/{len(coverage)} "
              f"logs (mean line coverage {sum(coverage) / len(coverage):.0%}).")


if __name__ == "__main__":
    main()
