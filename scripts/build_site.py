#!/usr/bin/env python3
"""Build both websites and Yomitan editions from a checked publication snapshot.

The snapshot lets GitHub Pages deploy without access to private local Anki
exports or model credentials. All snapshot members are digest checked first.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib
import shutil

from bugd.english import build_english_dictionary
from bugd.headword_readings import apply_catalog, load_catalog as load_reading_catalog
from bugd.imabi_lookup import apply_lookups, load_catalog, restore_lessons
from bugd.popup_lookup import apply_popup_lookups, load_overrides
from bugd.pipeline import run_build
from bugd.website import build_site
from bugd.site_links import SITE_URL


def read_json(path: pathlib.Path) -> dict:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def snapshot_inputs(directory: pathlib.Path) -> tuple[dict, dict, str]:
    manifest = read_json(directory / "manifest.json")
    for name, metadata in manifest["files"].items():
        if pathlib.PurePosixPath(name).name != name:
            raise ValueError("Unsafe publication snapshot member")
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != metadata["sha256"] or len(raw) != metadata["byteCount"]:
            raise ValueError(f"Publication snapshot digest mismatch: {name}")
    corpus = read_json(directory / "corpus.json.gz")
    corpus = restore_lessons(corpus, directory.parents[1] / "data/sources/imabi",
                             manifest.get("restoredImabiLessons", []))
    if "imabi-lookups.json" in manifest["files"]:
        corpus = apply_lookups(corpus, load_catalog(directory / "imabi-lookups.json"))
    if "popup-overrides.json" in manifest["files"]:
        corpus = apply_popup_lookups(corpus, load_overrides(directory / "popup-overrides.json"))
    if "headword-readings.json" in manifest["files"]:
        corpus = apply_catalog(corpus, load_reading_catalog(directory / "headword-readings.json"))
    if set(corpus["sourceLabels"]) != set(manifest["sources"]):
        raise ValueError("Publication snapshot is missing a source")
    if len(corpus["entries"]) != manifest["entries"]:
        raise ValueError("Publication snapshot entry count mismatch")
    return corpus, read_json(directory / "translations.en.json.gz"), manifest["revision"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=pathlib.Path)
    parser.add_argument("--corpus", type=pathlib.Path, default=pathlib.Path("data/merged/corpus.json"))
    parser.add_argument("--translations", type=pathlib.Path, default=pathlib.Path("data/translations/en.json"))
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("build/site"))
    parser.add_argument("--revision", default="2026.10.03")
    parser.add_argument("--original-only", action="store_true", help="build a local original-language preview")
    args = parser.parse_args()
    if args.snapshot:
        corpus, translations, revision = snapshot_inputs(args.snapshot)
    else:
        corpus, revision = read_json(args.corpus), args.revision
        translations = None if args.original_only else read_json(args.translations)
    result = build_site(corpus, args.output, translations=translations)
    merged_dir = args.output.parent / "site-corpus"
    merged_dir.mkdir(parents=True, exist_ok=True)
    (merged_dir / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False))
    dictionary_dir = args.output.parent / "site-dictionaries"
    result["originalDictionary"] = run_build(merged_dir=merged_dir, build_dir=dictionary_dir,
                                            revision=revision, require_entries=True,
                                            download_url=f"{SITE_URL}/downloads/bees-ultimate-grammar-dictionary.zip")
    downloads = args.output / "downloads"
    downloads.mkdir(exist_ok=True)
    shutil.copy2(result["originalDictionary"]["zipPath"], downloads)
    shutil.copy2(dictionary_dir / "banks" / "index.json", downloads / "index.json")
    if translations is not None:
        result["englishDictionary"] = build_english_dictionary(corpus, translations, dictionary_dir, revision=revision)
        shutil.copy2(result["englishDictionary"]["zipPath"], downloads)
        shutil.copy2(dictionary_dir / "index.en.json", downloads)
    sums = ''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in sorted(downloads.glob('*.zip')))
    (downloads / 'SHA256SUMS').write_text(sums)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
