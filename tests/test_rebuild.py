"""Rebuilding from the repository: committed extractions, acquisition, translations."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import pathlib
import subprocess
import tarfile
import zipfile

import pytest

from bugd.cli import main
from bugd.english import MODEL, PROMPT_VERSION, load_translation_cache
from bugd.sources import SourceLockError

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


acquire_sources = _script("acquire_sources")
verify_rebuild = _script("verify_rebuild")


def _entry(data: bytes, **extra) -> dict:
    return {"sha256": hashlib.sha256(data).hexdigest(), "byteCount": len(data), **extra}


def _lock(directory: pathlib.Path, files: dict, **extra) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SOURCE.lock.json").write_text(json.dumps({"source": directory.name, "files": files, **extra}))


def _args(tmp_path: pathlib.Path) -> list[str]:
    return ["--sources-dir", str(tmp_path / "sources"), "--extracted-dir", str(tmp_path / "extracted"),
            "--corrections-dir", str(tmp_path / "corrections"), "extract"]


def _committed(directory: pathlib.Path, payload: bytes, **override) -> None:
    directory.mkdir(parents=True)
    (directory / "extracted.json.gz").write_bytes(gzip.compress(payload, mtime=0))
    _lock(directory, {"deck.apkg": {"sha256": "0" * 64, "byteCount": 1}},
          extraction={"file": "extracted.json.gz", **_entry(payload), **override})


def test_a_lost_package_extracts_from_its_committed_extraction(tmp_path, capsys):
    payload = json.dumps({"source": "aiueo", "points": [{"source": "aiueo"}]}).encode()
    _committed(tmp_path / "sources" / "aiueo", payload)
    assert main(_args(tmp_path)) == 0
    assert (tmp_path / "extracted" / "aiueo.json").read_bytes() == payload
    report = json.loads(capsys.readouterr().out.split("[extract] ", 1)[1])
    assert report["committedExtractions"] == ["aiueo"]
    assert report["sources"]["aiueo"] == 1


def test_a_committed_extraction_that_drifted_fails_closed(tmp_path):
    payload = json.dumps({"source": "aiueo", "points": []}).encode()
    _committed(tmp_path / "sources" / "aiueo", payload, sha256="1" * 64)
    with pytest.raises(SourceLockError, match="does not match its lock"):
        main(_args(tmp_path))


def test_archive_members_are_found_in_zips_and_commit_tarballs():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("term_bank_1.json", b"[]")
        archive.writestr("other.txt", b"x")
    assert acquire_sources.archive_members(buffer.getvalue(), {"term_bank_1.json"}) == {"term_bank_1.json": b"[]"}

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo("repo-0123abc/src/lesson.md")
        info.size = 2
        archive.addfile(info, io.BytesIO(b"hi"))
    assert acquire_sources.archive_members(buffer.getvalue(), {"src/lesson.md"}) == {"src/lesson.md": b"hi"}


def test_acquire_downloads_missing_files_and_verifies_them(tmp_path):
    upstream = tmp_path / "upstream.json"
    upstream.write_bytes(b'{"ok":true}')
    source = tmp_path / "sources" / "dojg"
    _lock(source, {"index.json": _entry(upstream.read_bytes(), url=upstream.as_uri())})
    assert acquire_sources.acquire(source) == {"present": 0, "downloaded": 1}
    assert (source / "index.json").read_bytes() == upstream.read_bytes()
    assert acquire_sources.acquire(source) == {"present": 1, "downloaded": 0}


def test_acquire_extracts_locked_members_from_the_source_archive(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("term_bank_1.json", b"[1]")
    (tmp_path / "release.zip").write_bytes(buffer.getvalue())
    source = tmp_path / "sources" / "hjgp"
    _lock(source, {"term_bank_1.json": _entry(b"[1]")}, archive=(tmp_path / "release.zip").as_uri(),
          archiveSha256=hashlib.sha256(buffer.getvalue()).hexdigest(), archiveByteCount=len(buffer.getvalue()))
    assert acquire_sources.acquire(source)["downloaded"] == 1
    assert (source / "term_bank_1.json").read_bytes() == b"[1]"


def test_acquire_refuses_bytes_that_differ_from_the_lock(tmp_path):
    upstream = tmp_path / "upstream.json"
    upstream.write_bytes(b"changed upstream")
    source = tmp_path / "sources" / "dojg"
    _lock(source, {"index.json": {"sha256": "0" * 64, "byteCount": len(b"changed upstream"), "url": upstream.as_uri()}})
    with pytest.raises(acquire_sources.AcquireError, match="no longer serves the locked bytes"):
        acquire_sources.acquire(source)
    assert not (source / "index.json").exists()


def test_acquire_fails_for_an_input_with_no_download_and_no_committed_copy(tmp_path):
    source = tmp_path / "sources" / "kurabete"
    _lock(source, {"kurabete.zip": {"sha256": "0" * 64, "byteCount": 1}})
    with pytest.raises(acquire_sources.AcquireError, match="no download and no committed copy"):
        acquire_sources.acquire(source)


def test_acquire_accepts_a_lost_package_with_a_committed_extraction(tmp_path):
    source = tmp_path / "sources" / "aiueo"
    _committed(source, b"{}")
    assert acquire_sources.acquire(source)["committedExtraction"] == "extracted.json.gz"


def test_drive_links_are_recognised():
    match = acquire_sources.DRIVE.match("https://drive.google.com/file/d/1rtfXyyN8AQ4EfxT-ojVDqCBYhFLXIX5x/view")
    assert match.group(1) == "1rtfXyyN8AQ4EfxT-ojVDqCBYhFLXIX5x"


def test_every_source_is_committed_downloadable_or_extracted():
    """A fresh clone must be able to provide every locked input of every source."""
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "data/sources"],
                            capture_output=True, text=True, check=False)
    if listed.returncode:
        pytest.skip("not a git checkout")
    tracked = set(listed.stdout.splitlines())
    for lock_path in sorted((ROOT / "data" / "sources").glob("*/SOURCE.lock.json")):
        lock = json.loads(lock_path.read_text())
        source = lock_path.parent.name
        extraction = lock.get("extraction")
        if extraction:
            assert f"data/sources/{source}/{extraction['file']}" in tracked
            continue
        if lock.get("archive"):
            continue
        for name, entry in lock["files"].items():
            assert entry.get("url") or f"data/sources/{source}/{name}" in tracked, f"{source}/{name} has no source"


def test_the_translation_cache_starts_from_the_snapshot(tmp_path):
    header = {"model": MODEL, "promptVersion": PROMPT_VERSION}
    snapshot = tmp_path / "snapshot.json.gz"
    snapshot.write_bytes(gzip.compress(json.dumps({**header, "translations": {"a": "A", "b": "B"}}).encode()))
    local = tmp_path / "en.json"
    assert load_translation_cache(local, snapshot)["translations"] == {"a": "A", "b": "B"}
    local.write_text(json.dumps({**header, "translations": {"b": "B2", "c": "C"}}))
    assert load_translation_cache(local, snapshot)["translations"] == {"a": "A", "b": "B2", "c": "C"}
    local.write_text(json.dumps({**header, "model": "other", "translations": {}}))
    with pytest.raises(ValueError, match="different model"):
        load_translation_cache(local, snapshot)


def test_snapshot_comparison_ignores_only_gzip_encoding(tmp_path):
    def snapshot(directory: pathlib.Path, content: bytes, level: int, extra: str) -> None:
        directory.mkdir()
        raw = gzip.compress(content, compresslevel=level, mtime=0)
        (directory / "corpus.json.gz").write_bytes(raw)
        (directory / "catalog.json").write_text(extra)
        files = {"corpus.json.gz": {"sha256": hashlib.sha256(raw).hexdigest(), "byteCount": len(raw)}}
        (directory / "manifest.json").write_text(json.dumps({"revision": "1", "files": files}))

    content = json.dumps({"entries": list(range(500))}).encode()
    snapshot(tmp_path / "a", content, 9, "{}")
    snapshot(tmp_path / "b", content, 1, "{}")
    problems, notes = verify_rebuild.compare(tmp_path / "a", tmp_path / "b")
    assert problems == [] and len(notes) == 2
    snapshot(tmp_path / "c", content + b" ", 9, '{"x": 1}')
    problems, _ = verify_rebuild.compare(tmp_path / "a", tmp_path / "c")
    assert problems == ["catalog.json: differs", "corpus.json.gz: differs", "manifest.json: differs"]
