#!/usr/bin/env python3
"""Verify full release assets, source coverage and every published article link."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import pathlib
import re
import zipfile

from build_site import read_json, snapshot_inputs
from verify_popup import source_names as rendered_sources
from bugd.imabi_lookup import load_catalog
from bugd.popup_lookup import load_overrides, lookup_plan
from bugd.site_links import grammar_path, grammar_url
from bugd.sources import source_names
from bugd.sources.base import load_source_lock
from bugd.sources.imabi import ImabiExtractor
from bugd.validate import validate_zip
from bugd.website import source_label


def verify(snapshot: pathlib.Path, output: pathlib.Path, *, write_lock: bool = False) -> dict:
    corpus, _, revision = snapshot_inputs(snapshot)
    lookups = load_catalog(snapshot / "imabi-lookups.json")
    lookup_terms = {form for lesson in lookups.values() for form in lesson["expressions"]}
    old_expressions = {entry["expression"] for entry in read_json(snapshot / "corpus.json.gz")["entries"]}
    old_expressions.update(json.loads((snapshot / "published-headwords.json").read_text())["expressions"])
    plan = lookup_plan(corpus, load_overrides(snapshot / "popup-overrides.json"))
    if any(not item["forms"] for item in plan.values()):
        raise ValueError("Every published source record needs a Japanese lookup")
    source_coverage = {source: sum(key[0] == source for key in plan) for source in corpus["sourceLabels"]}
    required = set(source_names())
    if set(corpus["sourceLabels"]) != required:
        raise ValueError("Release snapshot must contain every registered source")
    points = [point for entry in corpus["entries"] for point in entry["contributions"]]
    if not required <= {point["source"] for point in points}:
        raise ValueError("A release source has no contributed records")

    source_dir = snapshot.parents[1] / "data/sources/imabi"
    extractor = ImabiExtractor(source_dir)
    source_lock = load_source_lock(source_dir)
    for name in source_lock:
        extractor.read_locked_bytes(name)
    acquired = json.loads((source_dir / "SOURCE.lock.json").read_text())
    listing = json.loads((source_dir / "index.json").read_text())
    page_files = {name for name in source_lock if name.startswith("pages/")}
    if listing["count"] != acquired["expectedTotal"] or len(page_files) != listing["count"]:
        raise ValueError("IMABI acquisition does not match its expected page count")
    if {page["file"] for page in listing["pages"]} != page_files:
        raise ValueError("IMABI index does not account for every locked page")
    extracted = extractor.extract()
    imabi_ids = {point["source_id"] for point in points if point["source"] == "imabi"}
    if imabi_ids != {point.source_id for point in extracted.points}:
        raise ValueError("Publication snapshot is missing an acquired IMABI lesson")

    downloads = output / "downloads"
    assets = {}
    checked_rows = {}
    for english, filename, index_name in (
        (False, "bees-ultimate-grammar-dictionary.zip", "index.json"),
        (True, "bees-ultimate-grammar-dictionary-en.zip", "index.en.json"),
    ):
        path = downloads / filename
        failures = validate_zip(path, require_entries=True)
        if failures:
            raise ValueError(f"Invalid {filename}: {failures}")
        count = 0
        expressions = set()
        imabi_terms = set()
        popup_sources = {}
        article_rows = {}
        with zipfile.ZipFile(path) as archive:
            index_bytes = archive.read("index.json")
            index = json.loads(index_bytes)
            if index["revision"] != revision:
                raise ValueError(f"Wrong revision in {filename}")
            if (downloads / index_name).read_bytes() != index_bytes:
                raise ValueError(f"Update index differs from {filename}")
            if not english:
                updater = snapshot.parents[1] / "dist/index.json"
                if json.loads(updater.read_text()) != index:
                    raise ValueError("Committed original update index differs from the release")
            for name in archive.namelist():
                if not re.fullmatch(r"term_bank_\d+\.json", name):
                    continue
                for row in json.loads(archive.read(name)):
                    expressions.add(row[0])
                    popup_sources.setdefault(row[0], set()).update(rendered_sources(row[5]))
                    if row[0] in lookup_terms and has_imabi_source(row[5]):
                        imabi_terms.add(row[0])
                    footer = row[5][0]["content"]["content"][-1]["content"]
                    if footer.get("href") != grammar_url(row[0], english=english):
                        raise ValueError(f"Wrong article link: {filename} {row[0]}")
                    article = output / grammar_path(row[0], english=english) / "index.html"
                    heading = f'<h1 lang="ja">{html.escape(row[0])}</h1>'
                    page = article.read_text() if article.is_file() else ""
                    if heading not in page:
                        raise ValueError(f"Missing article or wrong heading: {filename} {row[0]}")
                    article_rows[row[0]] = {html.unescape(uid) for uid in re.findall(r'data-source-row="([^"]+)"', page)}
                    count += 1
        if count != len(corpus["entries"]):
            raise ValueError(f"Entry count differs from full snapshot: {filename}")
        if not old_expressions <= expressions:
            raise ValueError(f"Previously published headwords were removed: {filename}")
        if lookup_terms != imabi_terms:
            raise ValueError(f"Missing IMABI lookups in {filename}: {sorted(lookup_terms - imabi_terms)}")
        for (_, row_uid), item in plan.items():
            label = source_label(item["point"], corpus["sourceLabels"])
            for form in item["forms"]:
                if label not in popup_sources.get(form, set()):
                    raise ValueError(f"Missing popup source {row_uid}: {filename} {form}")
                if row_uid not in article_rows.get(form, set()):
                    raise ValueError(f"Missing full source explanation {row_uid}: {filename} {form}")
        # The popup has a four-sense budget. Every indexed lesson must still be
        # reachable on the article, with its own title, in both editions.
        for form in sorted(lookup_terms):
            article = output / grammar_path(form, english=english) / "index.html"
            page = article.read_text()
            section = page.split('id="source-imabi"', 1)[-1].split('</section>', 1)[0]
            for lesson in lookups.values():
                if form in lesson["expressions"]:
                    heading = f'<h3 class="sense-heading">{html.escape(lesson["title"])}</h3>'
                    if heading not in section:
                        raise ValueError(f"Missing IMABI lesson {lesson['pageId']}: {filename} {form}")
        checked_rows[filename] = count

    sums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted(downloads.glob("*.zip"))
    )
    if (downloads / "SHA256SUMS").read_text() != sums:
        raise ValueError("Release SHA256SUMS does not match the actual archives")
    for name in (
        "bees-ultimate-grammar-dictionary.zip", "bees-ultimate-grammar-dictionary-en.zip",
        "index.json", "index.en.json", "SHA256SUMS",
    ):
        raw = (downloads / name).read_bytes()
        assets[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "byteCount": len(raw)}
    result = {"revision": revision, "sources": sorted(required), "entries": len(corpus["entries"]),
              "japaneseLookupRecords": source_coverage,
              "imabiLessons": len(imabi_ids), "imabiLookupLessons": len(lookups),
              "imabiLookupTerms": len(lookup_terms), "assets": assets}
    lock_path = snapshot / "release.json"
    if write_lock:
        lock_path.write_text(json.dumps(result, indent=2) + "\n")
    elif json.loads(lock_path.read_text()) != result:
        raise ValueError("Release bytes differ from website/data/release.json")
    return {"revision": revision, "sources": len(required), "imabiPages": listing["count"],
            "imabiLessons": len(imabi_ids), "imabiLookupLessons": len(lookups),
            "imabiLookupTerms": len(lookup_terms), "preservedHeadwords": len(old_expressions),
            "japaneseLookupRecords": source_coverage,
            "verifiedArticleLinks": checked_rows, "assets": assets}


def has_imabi_source(node: object) -> bool:
    if isinstance(node, list):
        return any(has_imabi_source(child) for child in node)
    if isinstance(node, dict):
        if "sourceName" in node.get("data", {}) and node.get("content") == "IMABI":
            return True
        return has_imabi_source(node.get("content"))
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=pathlib.Path, default=pathlib.Path("website/data"))
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("build/site"))
    parser.add_argument("--write-lock", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.snapshot, args.output, write_lock=args.write_lock), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
