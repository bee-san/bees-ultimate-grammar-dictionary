"""Literal Japanese lookup forms, separate from source alignment and notation.

Discontinuous patterns are indexed at their longest literal component(s), never
by joining words across a wildcard. English labels and ambiguous constructions
have reviewed, row-specific overrides. Original entries and URLs stay intact.
"""
from __future__ import annotations

import copy
import json
import pathlib
import re
import unicodedata
from collections import defaultdict

from .normalize import SENSE_MARKS
from .readings import is_exact_reading

DEFAULT_OVERRIDES = pathlib.Path(__file__).resolve().parents[2] / "website/data/popup-overrides.json"
PLAIN = re.compile(r"[\u3041-\u3096\u30a1-\u30fa\u30fc\u3400-\u9fff々〆]+\Z")
OPTIONAL = {"の", "に", "は", "も", "で", "と", "な", "だ", "よ", "て", "を", "が", "して", "だろう", "でしょう"}
_BRACKETS = re.compile(r"[（(]([^）)]*)[）)]")
_SLOTS = re.compile(r"(?:Noun|Verb|Adjective|Adjectives|Adj|Number|Amount|Particle|Question-phrase|counter|[ABNVXY])(?:\[[^]]*\])?", re.I)


def is_japanese_form(value: str) -> bool:
    return bool(PLAIN.fullmatch(value))


def literal_forms(value: str) -> list[str]:
    """Return surface forms or meaningful anchors explicitly present in a title."""
    value = "".join(c for c in value if c not in SENSE_MARKS)
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"^文型(?:・例文|\d*)[:：]", "", value)
    value = re.sub(r"<[^>]*>", "", value)
    value = re.sub(r"(?:自発動詞|疑問詞|数量|移動V)\s*", "~", value)
    forms = []
    pending = [value]
    while pending:
        text = pending.pop(0)
        match = _BRACKETS.search(text)
        if match:
            options = [""]
            if match[1] in OPTIONAL:
                options.append(match[1])
            pending.extend(text[:match.start()] + replacement + text[match.end():] for replacement in options)
            continue
        text = re.sub(r"\[([^]]*)\]", lambda m: m[1] if is_japanese_form(m[1]) else "~", text)
        text = _SLOTS.sub("~", text)
        # Do not treat a surviving English phrase as Japanese; it needs review.
        if re.search(r"[A-Za-z]", text):
            continue
        for alternative in re.split(r"[/／・⇒&＆、]|=>", text):
            alternative = alternative.replace("+", "")
            segments = [re.sub(r"\s+", "", part).strip("、。！!？?「」『』{}｛｝+＋:：0123456789")
                        for part in re.split(r"[~〜～…]|\.{2,}", alternative)]
            segments = [part for part in segments if is_japanese_form(part)]
            if segments:
                longest = max(map(len, segments))
                forms.extend(part for part in segments if len(part) == longest)
    return list(dict.fromkeys(forms))


def identity(point: dict) -> tuple[str, str]:
    return point["source"], point.get("row_uid") or point["source_id"]


#: Sources imported from producer Yomitan banks. Their `reading` column is the
#: key the producer's own dictionary was hovered with, so for a kana headword it
#: is the record's real surface form (`ずにはいる` is listed under
#: `ずにはいられない`). Scraped readings are not trusted this way: 日本語NET's
#: scraper concatenated alternatives (`かなかなあ`).
_READING_LOOKUP_SOURCES = {"edewakaru", "nihongo_no_sensei", "donna_toki"}
_KANA = re.compile(r"[\u3041-\u3096\u30a1-\u30fa\u30fc]+\Z")
_A_ROW = dict(zip("うくぐすつぬぶむる", "わかがさたなばまら"))


def _negated(lemma: str, surface: str) -> bool:
    """`surface` is the plain or potential negative of the kana `lemma`.

    These are the producers' synthetic lemmas: a negative construction is filed
    under an affirmative headword nobody writes (`もする` for `もしない`).
    """
    stem, last = lemma[:-1], lemma[-1:]
    candidates = set()
    if lemma.endswith("する"):
        candidates.add(lemma[:-2] + "しない")
    if last == "い":
        candidates.add(stem + "くない")
    if last == "る":
        candidates.update({stem + "ない", stem + "られない"})
    if last in _A_ROW:
        candidates.add(stem + _A_ROW[last] + "ない")
    return surface in candidates


def source_reading_form(point: dict) -> str | None:
    """The producer's own lookup key for a kana headword, when it differs."""
    expression = point.get("expression") or ""
    reading = (point.get("reading") or "").strip("〜～~")
    if (point.get("source") in _READING_LOOKUP_SOURCES and _KANA.fullmatch(expression)
            and _KANA.fullmatch(reading) and reading != expression):
        return reading
    return None


def negated_surface(point: dict) -> str | None:
    """The real negative form a producer's synthetic kana lemma stands for.

    The producer either spells it in the reading (`もする` read `もしない`) or
    keeps the lemma as its reading and lists the real form as a variant
    (`ずにはいられる`, variant `ずにはいられない`).
    """
    expression = point.get("expression") or ""
    if point.get("source") not in _READING_LOOKUP_SOURCES or not _KANA.fullmatch(expression):
        return None
    reading = (point.get("reading") or "").strip("〜～~")
    return next((form for form in [reading, *(point.get("variants") or [])]
                 if _negated(expression, form)), None)


def load_overrides(path: pathlib.Path = DEFAULT_OVERRIDES) -> dict[tuple[str, str], dict]:
    data = json.loads(path.read_text())
    if data.get("schemaVersion") != 1:
        raise ValueError("Unsupported popup lookup catalog")
    result = {}
    for record in data["records"]:
        key = record["source"], record["rowUid"]
        if key in result or not record["forms"] or any(not is_japanese_form(f) for f in record["forms"]):
            raise ValueError(f"Invalid popup override: {key}")
        result[key] = record
    return result


def lookup_plan(corpus: dict, overrides: dict) -> dict[tuple[str, str], dict]:
    """Plan every source record's literal/reading aliases without changing text."""
    result = {}
    for entry in corpus["entries"]:
        for point in entry["contributions"]:
            if point["source"] not in corpus["sourceLabels"]:
                continue
            key = identity(point)
            item = result.setdefault(key, {"point": point, "forms": [], "originals": []})
            item["originals"].append(entry["expression"])
            override = overrides.get(key)
            if override:
                if (point["source_id"] != override["sourceId"]
                        or point.get("meaning") != override.get("meaning")
                        or point.get("structure") != override.get("structure")):
                    raise ValueError(f"Stale popup override: {key}")
                forms = override["forms"]
            elif point["source"] == "imabi":
                forms = point.get("provenance", {}).get("lookupExpressions", [])
            else:
                forms = literal_forms(entry["expression"])
                # A reading of a discontinuous pattern is often a concatenation
                # of its pieces. Only use readings of contiguous written forms.
                if (len(forms) == 1 and re.search(r"[\u3400-\u9fff]", forms[0])
                        and not re.search(r"[~〜～…]|\.{2,}", entry["expression"].strip("~〜～"))):
                    reading = point.get("reading")
                    if (reading and len(literal_forms(reading)) == 1
                            and is_exact_reading(forms[0], literal_forms(reading)[0])):
                        forms = [*forms, *literal_forms(reading)]
                surface = source_reading_form(point)
                if surface:
                    forms = [*forms, surface]
                negative = negated_surface(point)
                if negative:
                    # A synthetic lemma is replaced by the form it stands for,
                    # unless the producer also titles the record with it
                    # (`〜きれる・〜きれない`).
                    declared = {re.sub(r"\s+", "", part).strip("〜～~") for variant in point.get("variants") or []
                                for part in re.split(r"[・／/]", variant)}
                    forms = [point["expression"], negative] if point["expression"] in declared else [negative]
            item["forms"] = list(dict.fromkeys([*item["forms"], *forms]))
    return result


def apply_popup_lookups(corpus: dict, overrides: dict | None = None, *, require_coverage: bool = True) -> dict:
    overrides = load_overrides() if overrides is None else overrides
    plan = lookup_plan(corpus, overrides)
    missing = [key for key, item in plan.items() if not item["forms"]]
    if missing and require_coverage:
        raise ValueError(f"Source records need Japanese popup lookups: {missing}")
    entries = [dict(entry, contributions=list(entry["contributions"])) for entry in corpus["entries"]]
    by_form = defaultdict(list)
    present = defaultdict(set)
    for entry in entries:
        by_form[entry["expression"]].append(entry)
        present[entry["expression"]].update(identity(p) for p in entry["contributions"])
    for key, item in sorted(plan.items()):
        point = item["point"]
        for form in item["forms"]:
            if key in present[form]:
                continue
            target = next((e for e in by_form[form] if any(
                not p.get("provenance", {}).get("aliasOf") for p in e["contributions"])), None)
            if target is None:
                target = {"expression": form, "variants": [], "contributions": []}
                entries.append(target)
                by_form[form].append(target)
            added = copy.deepcopy(point)
            # The source reading describes its whole pattern, not this anchor;
            # only another planned spelling that reads exactly as it does.
            added["reading"] = next((kana for kana in item["forms"] if kana != form and _KANA.fullmatch(kana)
                                     and is_exact_reading(form, kana)), None)
            added.setdefault("provenance", {}).update(popupLookupOf=point["expression"],
                                                      popupLookupRow=key[1])
            target["contributions"].append(added)
            present[form].add(key)
    # A Japanese headword none of its records is looked up by stays for its
    # published URL, but must not be reachable by conjugation or reading.
    for entry in entries:
        keys = {identity(p) for p in entry["contributions"]} & plan.keys()
        if keys and is_japanese_form(entry["expression"]) and not any(
                entry["expression"] in plan[key]["forms"] for key in keys):
            entry["lookup"] = False
    return dict(corpus, entries=entries)
