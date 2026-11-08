#!/usr/bin/env python3
"""Rebuild the dictionary from the repository alone and compare it with what is committed.

1. Export the committed tree (`git archive`, default `HEAD`) into a temporary
   directory, so no ignored, untracked or modified local file takes part.
2. In the export, download the locked sources that are not committed
   (`make acquire`), then extract, align and merge them (`make extract keymap
   merge`) and publish the snapshot over the committed one at its revision.
3. Compare the rebuilt snapshot with the committed snapshot: gzip files by
   content (zlib builds compress differently), the manifest with those gzip
   digests set aside, every other file byte for byte.
4. With a stock-zlib Python (as in CI), build both editions and check them
   against the committed release lock (`make release`). Under zlib-ng the
   archives cannot match the lock byte for byte, so this step is skipped; the
   snapshot content already determines them.

Usage:
    python3 scripts/verify_rebuild.py [--ref REF] [--workdir DIR] [--keep]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SNAPSHOT = "website/data"


def export(ref: str, destination: pathlib.Path, *paths: str) -> None:
    """Write the committed tree at `ref` (or some of its paths) into `destination`."""
    destination.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(["git", "-C", str(ROOT), "archive", "--format=tar", ref, *paths],
                               stdout=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        archive.extractall(destination, filter="data")
    if process.wait():
        raise SystemExit(f"git archive {ref} failed")


def run(step: str, command: list[str], cwd: pathlib.Path, timings: dict) -> None:
    print(f"== {step}: {' '.join(command)}", flush=True)
    started = time.monotonic()
    environment = dict(os.environ, PYTHONPATH="src", PYTHONHASHSEED="0", TZ="UTC",
                       LC_ALL="C.UTF-8", SOURCE_DATE_EPOCH="0")
    environment.pop("MAKEFLAGS", None)
    subprocess.run(command, cwd=cwd, env=environment, check=True)
    timings[step] = round(time.monotonic() - started)


def gunzip_digest(path: pathlib.Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def comparable_manifest(directory: pathlib.Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text())
    for name, entry in manifest["files"].items():
        if name.endswith(".gz"):
            manifest["files"][name] = {"contentSha256": gunzip_digest(directory / name)}
    return manifest


def compare(committed: pathlib.Path, rebuilt: pathlib.Path) -> tuple[list[str], list[str]]:
    """Differences between two snapshot directories, and benign notes."""
    def files(directory: pathlib.Path) -> set[str]:
        return {str(path.relative_to(directory)) for path in directory.rglob("*") if path.is_file()}

    problems, notes = [], []
    left, right = files(committed), files(rebuilt)
    problems += [f"{name}: missing from the rebuild" for name in sorted(left - right)]
    problems += [f"{name}: not in the committed snapshot" for name in sorted(right - left)]
    for name in sorted(left & right):
        a, b = committed / name, rebuilt / name
        if a.read_bytes() == b.read_bytes():
            continue
        if name.endswith(".gz") and gunzip_digest(a) == gunzip_digest(b):
            notes.append(f"{name}: same content, different gzip bytes")
        elif name == "manifest.json" and comparable_manifest(committed) == comparable_manifest(rebuilt):
            notes.append(f"{name}: same apart from gzip digests")
        else:
            problems.append(f"{name}: differs")
    return problems, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", default="HEAD", help="committed revision to rebuild (default: HEAD)")
    parser.add_argument("--workdir", type=pathlib.Path, help="where to rebuild (default: a temporary directory)")
    parser.add_argument("--keep", action="store_true", help="keep the work directory afterwards")
    args = parser.parse_args()

    workdir = args.workdir or pathlib.Path(tempfile.mkdtemp(prefix="bugd-rebuild-"))
    if workdir.exists() and any(workdir.iterdir()):
        parser.error(f"{workdir} is not empty")
    tree, committed = workdir / "repo", workdir / "committed"
    python, timings = sys.executable, {}
    try:
        export(args.ref, tree)
        export(args.ref, committed, SNAPSHOT)
        make = ["make", "-j1", f"PY={python}"]
        run("acquire", [*make, "acquire"], tree, timings)
        run("pipeline", [*make, "extract", "keymap", "merge"], tree, timings)
        run("publish", [python, "scripts/publish_snapshot.py"], tree, timings)
        problems, notes = compare(committed / SNAPSHOT, tree / SNAPSHOT)
        stock_zlib = "ng" not in zlib.ZLIB_RUNTIME_VERSION
        if not problems and stock_zlib:
            run("release", [*make, "release"], tree, timings)
        result = {"ref": args.ref, "snapshotMatches": not problems, "differences": problems, "notes": notes,
                  "releaseLockChecked": not problems and stock_zlib, "seconds": timings}
        if not stock_zlib:
            result["notes"].append(f"release lock not checked: zlib {zlib.ZLIB_RUNTIME_VERSION} is not stock zlib")
        print(json.dumps(result, indent=2))
        return 1 if problems else 0
    except subprocess.CalledProcessError as error:
        print(f"rebuild failed at: {' '.join(error.cmd)}", file=sys.stderr)
        return 1
    finally:
        if args.keep or args.workdir:
            print(f"work directory kept: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
