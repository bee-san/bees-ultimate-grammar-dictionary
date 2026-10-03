#!/usr/bin/env python3
"""Freeze complete corpus and Luna translations for reproducible Pages builds."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib

from bugd.english import MODEL, collect_requests, english_corpus
from bugd.sources import source_names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=pathlib.Path, default=pathlib.Path("data/merged/corpus.json"))
    parser.add_argument("--translations", type=pathlib.Path, default=pathlib.Path("data/translations/en.json"))
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("website/data"))
    parser.add_argument("--revision", default="2026.10.03")
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text())
    cache = json.loads(args.translations.read_text())
    missing = set(source_names()) - set(corpus["sourceLabels"])
    if missing:
        raise ValueError(f"Refusing to publish a partial dictionary; missing sources: {sorted(missing)}")
    english_corpus(corpus, cache)  # Completeness gate, before writing any files.
    requests = collect_requests([p for e in corpus["entries"] for p in e["contributions"]])
    cache = dict(cache, translations={key: cache["translations"][key] for key in requests})
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {"revision": args.revision, "model": MODEL, "sources": sorted(corpus["sourceLabels"]),
                "entries": len(corpus["entries"]), "translations": len(cache["translations"]), "files": {}}
    for name, data in (("corpus.json.gz", corpus), ("translations.en.json.gz", cache)):
        raw = gzip.compress((json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(), mtime=0)
        (args.output / name).write_bytes(raw)
        manifest["files"][name] = {"sha256": hashlib.sha256(raw).hexdigest(), "byteCount": len(raw)}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
