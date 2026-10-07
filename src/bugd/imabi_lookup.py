"""Explicit IMABI lesson-to-lookup links, without equating different lessons.

An IMABI lesson may discuss several forms, and several lessons may discuss one
particle. These are indexing links, not evidence that the forms or senses are
interchangeable. Apply them after alignment, keeping every original entry and
its permanent URL. Both acquired-source builds and frozen releases use this
same projection.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import pathlib
import re

DEFAULT_CATALOG = pathlib.Path(__file__).resolve().parents[2] / "website/data/imabi-lookups.json"
_FORM = re.compile(r"[\u3041-\u3096\u30a1-\u30fa\u30fc\u3400-\u9fff々〆]+\Z")


def restore_lessons(corpus: dict, source_dir: pathlib.Path, page_ids: list[str]) -> dict:
    """Restore explicitly named lessons from digest-locked raw pages.

    The old snapshot excluded page 535 as site metadata because it was called
    'About'. It actually teaches について/に関して/をめぐって. Append its
    identity to preserve every existing publication row UID.
    """
    from .pipeline import point_to_json
    from .sources.imabi import ImabiExtractor
    existing = {p["source_id"] for e in corpus["entries"] for p in e["contributions"] if p["source"] == "imabi"}
    needed = set(page_ids) - existing
    if not needed:
        return corpus
    points = {p.source_id: p for p in ImabiExtractor(source_dir).extract().points}
    ordinal = max(int(p["row_uid"].split(":")[1]) for e in corpus["entries"]
                  for p in e["contributions"] if p["source"] == "imabi")
    entries = list(corpus["entries"])
    for page_id in sorted(needed, key=int):
        ordinal += 1
        point = dataclasses.replace(points[page_id], row_uid=f"imabi:{ordinal}")
        entries.append({"expression": point.expression, "variants": [], "contributions": [point_to_json(point)]})
    return dict(corpus, entries=entries)


def load_catalog(path: pathlib.Path = DEFAULT_CATALOG) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1:
        raise ValueError("Unsupported IMABI lookup catalog")
    result = {}
    for lesson in data["lessons"]:
        page_id = lesson["pageId"]
        forms = lesson["expressions"]
        if (not isinstance(page_id, str) or not re.fullmatch(r"[1-9][0-9]*", page_id)
                or page_id in result or not lesson["title"].strip()
                or not forms or len(forms) != len(set(forms))
                or any(not _FORM.fullmatch(form) for form in forms)):
            raise ValueError(f"Invalid IMABI lookup catalog record: {page_id}")
        for written, kana in lesson.get("readingAliases", {}).items():
            if written not in forms or kana not in forms or not re.fullmatch(r"[ぁ-ゖー]+", kana):
                raise ValueError(f"Invalid IMABI kana alias: {page_id} {written}")
        result[page_id] = lesson
    return result


def apply_lookups(corpus: dict, catalog: dict[str, dict] | None = None) -> dict:
    """Add full, attributed lessons to exact Japanese lookup rows, idempotently.

    With a catalog, enrich an older frozen corpus and fail on missing lessons.
    Without one, use the lookupExpressions captured by the source extractor. Never
    alter cross-source alignment, overwrite explanations, or remove old headwords.
    """
    entries = []
    lessons = {}
    by_expression: dict[str, list[dict]] = {}
    for original in corpus["entries"]:
        entry = dict(original, contributions=[])
        for original_point in original["contributions"]:
            point = original_point
            if point["source"] == "imabi":
                page_id = point["source_id"]
                metadata = catalog.get(page_id) if catalog is not None else None
                provenance = dict(point.get("provenance", {}))
                if metadata:
                    provenance.update(lessonTitle=metadata["title"],
                                      lookupExpressions=metadata["expressions"])
                point = dict(point, provenance=provenance)
                if provenance.get("lookupExpressions"):
                    lessons.setdefault(page_id, point)
            entry["contributions"].append(point)
        entries.append(entry)
        by_expression.setdefault(entry["expression"], []).append(entry)
    if catalog is not None and set(catalog) - set(lessons):
        raise ValueError(f"Missing IMABI lookup lessons: {sorted(set(catalog) - set(lessons))}")

    for page_id, point in sorted(lessons.items(), key=lambda item: int(item[0])):
        for expression in point["provenance"]["lookupExpressions"]:
            targets = by_expression.get(expression, [])
            if any(p["source"] == "imabi" and p["source_id"] == page_id
                   for entry in targets for p in entry["contributions"]):
                continue
            # Keep redirect-only rows intact. A separate real row can coexist at
            # the same spelling without swallowing the redirect's other sources.
            target = next((entry for entry in targets if any(
                not p.get("provenance", {}).get("aliasOf")
                for p in entry["contributions"])), None)
            if target is None:
                target = {"expression": expression, "variants": [], "contributions": []}
                entries.append(target)
                by_expression.setdefault(expression, []).append(target)
            target["contributions"].append(copy.deepcopy(point))
    return dict(corpus, entries=entries)
