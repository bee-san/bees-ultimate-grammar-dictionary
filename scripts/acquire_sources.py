#!/usr/bin/env python3
"""Fetch every locked source input a fresh clone lacks, from its pinned URL.

Each `data/sources/<name>/SOURCE.lock.json` pins its files by SHA-256 and byte
count. A file already on disk with the pinned digest is kept. A missing file is
downloaded from where its lock says it lives:

* a file `url` (GitHub raw at a pinned commit, NINJAL's repository);
* a Google Drive `url`, fetched as parallel byte ranges (Drive throttles a single
  connection);
* the source's `archive` (a GitHub release ZIP or a commit tarball), whose
  members are the locked files.

Every download is checked against the lock before it is written. Inputs that
have no live public download are committed instead (see SOURCES.md), and a
source whose raw package is gone ships the extraction its lock pins as
`extraction`. Anything else missing is an error: the rebuild would be partial.

Usage:
    python3 scripts/acquire_sources.py [--source NAME]...
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import io
import json
import pathlib
import re
import sys
import tarfile
import time
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources"
USER_AGENT = "bees-ultimate-grammar-dictionary/acquire (+https://github.com/bee-san/bees-ultimate-grammar-dictionary)"
TIMEOUT = 120
ATTEMPTS = 5
DRIVE = re.compile(r"^https://drive\.google\.com/file/d/([\w-]+)")
DRIVE_PART_BYTES = 4 << 20


class AcquireError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def matches(data: bytes, entry: dict) -> bool:
    return len(data) == entry["byteCount"] and digest(data) == entry["sha256"]


def fetch(url: str, *, limit: int, byte_range: tuple[int, int] | None = None) -> bytes:
    """GET `url` (optionally one inclusive byte range), retrying transient failures."""
    headers = {"User-Agent": USER_AGENT}
    if byte_range:
        headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
    error: Exception | None = None
    for attempt in range(ATTEMPTS):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT) as response:
                data = response.read(limit + 1)
            if len(data) > limit:
                raise AcquireError(f"{url} returned more than the {limit} bytes expected")
            if byte_range and len(data) != byte_range[1] - byte_range[0] + 1:
                raise OSError(f"short range read from {url}")
            return data
        except AcquireError:
            raise
        except Exception as caught:  # noqa: BLE001 - network errors are retried, then reported
            error = caught
            time.sleep(2 ** attempt)
    raise AcquireError(f"could not download {url}: {error}")


def fetch_drive(file_id: str, size: int) -> bytes:
    """A public Drive file, as parallel byte ranges of a known total size."""
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    ranges = [(start, min(start + DRIVE_PART_BYTES, size) - 1) for start in range(0, size, DRIVE_PART_BYTES)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        parts = list(pool.map(lambda r: fetch(url, limit=r[1] - r[0] + 1, byte_range=r), ranges))
    return b"".join(parts)


def download(url: str, entry: dict) -> bytes:
    drive = DRIVE.match(url)
    return fetch_drive(drive.group(1), entry["byteCount"]) if drive else fetch(url, limit=entry["byteCount"])


def archive_members(raw: bytes, wanted: set[str]) -> dict[str, bytes]:
    """The `wanted` members of a ZIP or gzip tarball, by locked path.

    A commit tarball nests everything below one `<repo>-<sha>/` directory, so a
    member also matches with its first path component removed.
    """
    found: dict[str, bytes] = {}

    def take(name: str, read) -> None:
        for candidate in (name, name.split("/", 1)[-1]):
            if candidate in wanted and candidate not in found:
                found[candidate] = read()
                return

    if raw[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for info in archive.infolist():
                if not info.is_dir():
                    take(info.filename, lambda info=info: archive.read(info))
    else:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            for member in archive:
                if member.isfile():
                    take(member.name, lambda member=member: archive.extractfile(member).read())
    return found


def write(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(data)
    temporary.replace(path)


def acquire(directory: pathlib.Path) -> dict:
    """Make one source's locked files present; return what happened."""
    lock = json.loads((directory / "SOURCE.lock.json").read_text(encoding="utf-8"))
    files: dict[str, dict] = lock["files"]
    report = {"present": 0, "downloaded": 0}
    missing: dict[str, dict] = {}
    for name, entry in files.items():
        path = directory / name
        if path.is_file():
            if not matches(path.read_bytes(), entry):
                raise AcquireError(f"{path} does not match its lock; delete it to re-acquire")
            report["present"] += 1
        else:
            missing[name] = entry
    if not missing:
        return report

    if lock.get("archive"):
        raw = fetch(lock["archive"], limit=lock.get("archiveByteCount") or 256 << 20)
        if lock.get("archiveSha256") and digest(raw) != lock["archiveSha256"]:
            # Forges may regenerate archives; the locked members still decide.
            print(f"  note: {lock['archive']} has a new archive digest; checking its members", file=sys.stderr)
        members = archive_members(raw, set(missing))
        for name in sorted(missing):
            data = members.get(name)
            if data is None or not matches(data, missing[name]):
                raise AcquireError(f"{directory.name}/{name}: not in {lock['archive']} with the locked digest")
            write(directory / name, data)
            report["downloaded"] += 1
        return report

    unavailable = []
    for name, entry in sorted(missing.items()):
        if not entry.get("url"):
            unavailable.append(name)
            continue
        data = download(entry["url"], entry)
        if not matches(data, entry):
            raise AcquireError(f"{directory.name}/{name}: {entry['url']} no longer serves the locked bytes")
        write(directory / name, data)
        report["downloaded"] += 1
    if unavailable:
        extraction = lock.get("extraction")
        if not extraction or not (directory / extraction["file"]).is_file():
            raise AcquireError(f"{directory.name}: no download and no committed copy for {', '.join(unavailable)}")
        report["committedExtraction"] = extraction["file"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", action="append", help="acquire only this source (repeatable)")
    parser.add_argument("--sources-dir", type=pathlib.Path, default=SOURCES)
    args = parser.parse_args()
    directories = sorted(path.parent for path in args.sources_dir.glob("*/SOURCE.lock.json"))
    if args.source:
        unknown = set(args.source) - {path.name for path in directories}
        if unknown:
            parser.error(f"unknown source(s): {', '.join(sorted(unknown))}")
        directories = [path for path in directories if path.name in args.source]
    failed = False
    for directory in directories:
        try:
            print(f"{directory.name}: {json.dumps(acquire(directory))}", flush=True)
        except AcquireError as error:
            failed = True
            print(f"{directory.name}: FAILED {error}", file=sys.stderr, flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
