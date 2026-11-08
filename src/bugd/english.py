"""Content-addressed Luna translations and the separate English corpus.

The original corpus is never rewritten. Missing or stale translations fail the
English build, rather than silently leaving Japanese explanations in it.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import pathlib
import re
from collections.abc import Iterator

MODEL = "gpt-6-luna"
PROMPT_VERSION = 1
MONOLINGUAL_SOURCES = {"bunpou", "edewakaru", "hjgp", "kurabete", "nihongo_net", "nihongo_no_sensei", "ninjal_bunkei"}
FIELDS = ("meaning", "structure", "nuance", "explanation", "notes")
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_LATIN_WORDS = re.compile(r"[A-Za-z]{3,}")


#: Sources whose prose quotes judged Japanese sentences on lines marked ○ or ×.
#: The judgement is about the Japanese wording, so the English edition keeps it.
JUDGED_SENTENCE_SOURCES = {"kurabete"}
_JUDGED = ("○", "×")


def restore_judged_sentences(original: str, translated: str) -> str:
    """Keep each ○/× Japanese sentence beside its English translation.

    Luna translates most judged sentences into English only, which loses the
    contrast they illustrate (`×After studying hard, …`). Lines are paired in
    order; when the counts differ the translation is returned unchanged.
    """
    source = [line for line in original.split("\n") if line[:1] in _JUDGED]
    lines = translated.split("\n")
    targets = [index for index, line in enumerate(lines) if line[:1] in _JUDGED]
    if not source or len(source) != len(targets):
        return translated
    for japanese, index in zip(source, targets):
        english = lines[index]
        if english[:1] != japanese[:1] or japanese[1:].strip() in english:
            continue
        lines[index] = f"{japanese} — {english[1:].strip()}"
    return "\n".join(lines)


#: The translations the committed publication snapshot ships.
SNAPSHOT_CACHE = pathlib.Path(__file__).resolve().parents[2] / "website/data/translations.en.json.gz"


def load_translation_cache(path: pathlib.Path, snapshot: pathlib.Path = SNAPSHOT_CACHE) -> dict:
    """The local translation cache, on top of the translations the snapshot ships.

    `data/translations/` is not committed, so a fresh clone starts from the
    snapshot's translations and only text that changed needs a model call.
    """
    cache = {"model": MODEL, "promptVersion": PROMPT_VERSION, "translations": {}}
    for layer in (snapshot, path):
        if not layer.is_file():
            continue
        raw = layer.read_bytes()
        data = json.loads(gzip.decompress(raw) if layer.suffix == ".gz" else raw)
        if data.get("model") != MODEL or data.get("promptVersion") != PROMPT_VERSION:
            raise ValueError(f"Translation cache {layer} has a different model or prompt version")
        cache["translations"].update(data["translations"])
    return cache


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
                    if point["source"] in JUDGED_SENTENCE_SOURCES:
                        translated = restore_judged_sentences(text, translated)
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


def build_english_dictionary(corpus: dict, cache: dict, output, *, revision: str,
                             media: dict[str, bytes] | None = None) -> dict:
    """Build and validate a separately installable English Yomitan edition.

    `media` holds the pictures the corpus names (see `bugd.illustrations.with_media`).
    """
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
                              tag_bank=build_tag_bank(labels), styles_css=STYLES_CSS, media=media)
    path.write_bytes(build_zip(members))
    failures = validate_zip(path, require_entries=True)
    if failures:
        raise SchemaValidationError(path, failures)
    (output / "index.en.json").write_text(members["index.json"], encoding="utf-8")
    return {"zipPath": str(path), "entries": len(entries), "translations": len(cache["translations"])}
