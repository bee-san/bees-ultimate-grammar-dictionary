#!/usr/bin/env python3
"""Freeze complete corpus and Luna translations for reproducible Pages builds.

The snapshot stores the merged corpus *before* the IMABI, popup and reading
projections; `build_site.py` applies those from the committed catalogs. It is
rebuilt from `data/merge/unified.jsonl` because `data/merged/corpus.json` is
already projected, and projecting twice reorders IMABI contributions.

Illustrations are encoded from the locked 絵でわかる日本語 archive into
`illustrations/` and pinned by `illustrations.json` (see `bugd.illustrations`).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib

from bugd import illustrations, unify
from bugd.english import MODEL, collect_requests, english_corpus, load_translation_cache
from bugd.headword_readings import CATALOG as READING_CATALOG, apply_catalog, load_catalog as load_reading_catalog
from bugd.imabi_lookup import DEFAULT_CATALOG, apply_lookups, load_catalog, restore_lessons
from bugd.pipeline import entry_to_json
from bugd.popup_lookup import DEFAULT_OVERRIDES, apply_popup_lookups, load_overrides
from bugd.sources import source_names
from bugd.sources.edewakaru import ILLUSTRATED_ARCHIVE, EdewakaruExtractor

ROOT = pathlib.Path(__file__).resolve().parents[1]


def base_corpus(unified: pathlib.Path, merged: pathlib.Path) -> dict:
    entries = unify.to_merged_entries(unify.read_unified(unified))
    labels = json.loads(merged.read_text())["sourceLabels"]
    return {"sourceLabels": labels, "entries": [entry_to_json(entry) for entry in entries]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unified", type=pathlib.Path, default=unify.DEFAULT_UNIFIED_PATH)
    parser.add_argument("--corpus", type=pathlib.Path, default=pathlib.Path("data/merged/corpus.json"),
                        help="merged corpus, read for its source labels")
    parser.add_argument("--translations", type=pathlib.Path, default=pathlib.Path("data/translations/en.json"))
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("website/data"))
    parser.add_argument("--revision", help="new snapshot revision (default: keep the current one)")
    args = parser.parse_args()
    previous_path = args.output / "manifest.json"
    previous = json.loads(previous_path.read_text()) if previous_path.is_file() else {}
    args.revision = args.revision or previous.get("revision")
    if not args.revision:
        parser.error("--revision is required for a new snapshot")
    restored = previous.get("restoredImabiLessons", [])

    corpus = base_corpus(args.unified, args.corpus)
    cache = load_translation_cache(args.translations)
    missing = set(source_names()) - set(corpus["sourceLabels"])
    if missing:
        raise ValueError(f"Refusing to publish a partial dictionary; missing sources: {sorted(missing)}")
    # The same projection, in the same order, as build_site.snapshot_inputs.
    indexed = restore_lessons(json.loads(json.dumps(corpus)), ROOT / "data/sources/imabi", restored)
    indexed = apply_lookups(indexed, load_catalog())
    indexed = apply_popup_lookups(indexed, load_overrides())
    indexed = apply_catalog(indexed, load_reading_catalog())
    english_corpus(indexed, cache)  # Completeness gate, before writing any files.
    requests = collect_requests([p for e in indexed["entries"] for p in e["contributions"]])
    cache = dict(cache, translations={key: cache["translations"][key] for key in requests})

    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {"revision": args.revision, "model": MODEL, "sources": sorted(corpus["sourceLabels"]),
                "entries": len(indexed["entries"]), "translations": len(cache["translations"]), "files": {}}
    for name, data in (("corpus.json.gz", corpus), ("translations.en.json.gz", cache)):
        raw = gzip.compress((json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(), mtime=0)
        (args.output / name).write_bytes(raw)
        manifest["files"][name] = {"sha256": hashlib.sha256(raw).hexdigest(), "byteCount": len(raw)}
    for path in (DEFAULT_CATALOG, DEFAULT_OVERRIDES, DEFAULT_CATALOG.with_name("published-headwords.json"),
                 READING_CATALOG):
        raw = path.read_bytes()
        if path.parent.resolve() != args.output.resolve():
            (args.output / path.name).write_bytes(raw)
        manifest["files"][path.name] = {"sha256": hashlib.sha256(raw).hexdigest(), "byteCount": len(raw)}
    # Every picture a contribution names, encoded from the locked archive.
    archive = EdewakaruExtractor(ROOT / "data/sources/edewakaru").read_locked_bytes(ILLUSTRATED_ARCHIVE)
    previous_catalog = args.output / illustrations.CATALOG_NAME
    catalog = illustrations.build(
        illustrations.referenced(corpus), {"edewakaru": archive}, args.output,
        previous=json.loads(previous_catalog.read_text()) if previous_catalog.is_file() else None,
    )
    raw = illustrations.write_catalog(catalog, args.output)
    manifest["files"][illustrations.CATALOG_NAME] = {"sha256": hashlib.sha256(raw).hexdigest(), "byteCount": len(raw)}
    manifest["illustrations"] = len(catalog["images"])
    if restored:
        manifest["restoredImabiLessons"] = restored
    previous_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
