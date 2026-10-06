"""Content-addressed Luna translations and the separate English corpus.

The original corpus is never rewritten. Missing or stale translations fail the
English build, rather than silently leaving Japanese explanations in it.
"""

from __future__ import annotations

import copy
import hashlib
import re
from collections.abc import Iterator

MODEL = "gpt-6-luna"
PROMPT_VERSION = 1
MONOLINGUAL_SOURCES = {"bunpou", "edewakaru", "hjgp", "nihongo_net", "nihongo_no_sensei", "ninjal_bunkei"}
FIELDS = ("meaning", "structure", "nuance", "explanation", "notes")
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_LATIN_WORDS = re.compile(r"[A-Za-z]{3,}")


def translation_key(text: str, kind: str = "definition") -> str:
    return hashlib.sha256(f"{PROMPT_VERSION}:{kind}:{text}".encode("utf-8")).hexdigest()


def needs_translation(text: object, *, monolingual: bool = False) -> bool:
    if not isinstance(text, str) or not _CJK.search(text):
        return False
    # English-authored explanations often quote Japanese. They already have an
    # English reader; source-declared monolingual prose is translated in full.
    return monolingual or len(_LATIN_WORDS.findall(text)) < 3


def point_requests(point: dict) -> Iterator[tuple[str, str, str]]:
    mono = point["source"] in MONOLINGUAL_SOURCES
    for field in FIELDS:
        text = point.get(field)
        if needs_translation(text, monolingual=mono):
            yield field, "definition", text
    for field in ("nuance", "explanation"):
        if not point.get(field) and point.get(field + "_ja"):
            yield field + "_ja", "definition", point[field + "_ja"]
    for index, example in enumerate(point.get("examples", [])):
        if not example.get("english") and not example.get("ai_generated"):
            yield f"example:{index}", "sentence", example["japanese"]


def collect_requests(points: list[dict]) -> dict[str, dict]:
    result = {}
    for point in points:
        for field, kind, text in point_requests(point):
            key = translation_key(text, kind)
            result.setdefault(key, {"id": key, "kind": kind, "text": text,
                                    "grammar": point["expression"], "field": field})
    return result


def english_corpus(corpus: dict, cache: dict) -> dict:
    if cache.get("model") != MODEL or cache.get("promptVersion") != PROMPT_VERSION:
        raise ValueError("English translations must use gpt-6-luna and the current prompt version")
    translations = cache.get("translations", {})
    result = copy.deepcopy(corpus)
    for entry in result["entries"]:
        for point in entry["contributions"]:
            originals = {}
            translated_examples = 0
            for field, kind, text in list(point_requests(point)):
                key = translation_key(text, kind)
                translated = translations.get(key)
                if not isinstance(translated, str) or not translated.strip():
                    raise ValueError(f"Missing English translation: {point['source']} {point['expression']} {field} ({key})")
                if field.startswith("example:"):
                    point["examples"][int(field.split(":")[1])]["english"] = translated
                    translated_examples += 1
                else:
                    originals[field] = text
                    point[field.removesuffix("_ja")] = translated
            # Source-authored English counterparts take precedence. The English
            # website retains the complete original as a disclosure separately.
            point["nuance_ja"] = None
            point["explanation_ja"] = None
            if originals or translated_examples:
                point.setdefault("provenance", {})["englishTranslation"] = {
                    "model": MODEL, "promptVersion": PROMPT_VERSION, "original": originals,
                    "exampleCount": translated_examples,
                }
    result["edition"] = "en"
    result["translationModel"] = MODEL
    return result


def build_english_dictionary(corpus: dict, cache: dict, output, *, revision: str) -> dict:
    """Build and validate a separately installable English Yomitan edition."""
    import pathlib
    from .banks import build_banks, build_index, build_tag_bank
    from .package import build_zip, package_members
    from .pipeline import entry_from_json, SchemaValidationError
    from .site_links import SITE_URL, grammar_url
    from .styles import STYLES_CSS
    from .validate import validate_zip

    translated = english_corpus(corpus, cache)
    entries = [entry_from_json(entry) for entry in translated["entries"]]
    labels = corpus.get("sourceLabels", {})
    filename = "bees-ultimate-grammar-dictionary-en.zip"
    index = build_index(revision, source_labels=labels,
                        index_url=f"{SITE_URL}/downloads/index.en.json",
                        download_url=f"{SITE_URL}/downloads/{filename}")
    index["title"] += " (English)"
    index["url"] = f"{SITE_URL}/en/"
    index["description"] = "English edition with GPT-6 Luna translations of monolingual explanations and examples. Original wording is available on each linked grammar page."
    index["attribution"] = index.get("attribution", "") + " English translations: GPT-6 Luna."
    banks = build_banks(entries)
    for bank in banks.values():
        for row in bank:
            footer = row[5][0]["content"]["content"][-1]
            footer["content"]["href"] = grammar_url(row[0], english=True)
    output = pathlib.Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / filename
    members = package_members(index=index, banks=banks,
                              tag_bank=build_tag_bank(labels), styles_css=STYLES_CSS)
    path.write_bytes(build_zip(members))
    failures = validate_zip(path, require_entries=True)
    if failures:
        raise SchemaValidationError(path, failures)
    (output / "index.en.json").write_text(members["index.json"], encoding="utf-8")
    return {"zipPath": str(path), "entries": len(entries), "translations": len(cache["translations"])}
