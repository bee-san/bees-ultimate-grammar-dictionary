"""Reviewed readings for kanji headwords that no source spells exactly.

A popup prints a row's reading as furigana and matches hovered kana text by it.
Sources supply most readings; `website/data/headword-readings.json` supplies
the rest from JMdict, Sudachi and Jiten (see `scripts/resolve_headword_readings.py`).
Every reading, from either place, must spell its headword exactly.
"""
from __future__ import annotations

import json
import pathlib

from .popup_lookup import is_japanese_form
from .readings import has_kanji, is_exact_reading

CATALOG = pathlib.Path(__file__).resolve().parents[2] / "website/data/headword-readings.json"


def source_reading(expression: str, readings) -> str:
    """The first contributed reading that is an exact kana spelling of the headword."""
    for reading in readings:
        candidate = (reading or "").strip("〜～~")
        if candidate and is_exact_reading(expression, candidate):
            return candidate
    return ""


def needs_reading(entry: dict) -> bool:
    expression = entry["expression"]
    return (entry.get("lookup", True) is not False and is_japanese_form(expression) and has_kanji(expression)
            and not source_reading(expression, (p.get("reading") for p in entry["contributions"])))


def load_catalog(path: pathlib.Path = CATALOG) -> dict[str, str]:
    data = json.loads(path.read_text())
    if data.get("schemaVersion") != 1:
        raise ValueError("Unsupported headword reading catalog")
    result = {}
    for expression, record in data["records"].items():
        reading = record.get("reading")
        if reading is None:
            continue
        if not is_exact_reading(expression, reading):
            raise ValueError(f"Catalog reading does not spell its headword: {expression} {reading}")
        result[expression] = reading
    return result


def apply_catalog(corpus: dict, catalog: dict[str, str]) -> dict:
    """Give each headword that lacks an exact source reading its catalog reading."""
    entries = []
    for entry in corpus["entries"]:
        if needs_reading(entry) and entry["expression"] in catalog:
            entry = dict(entry, reading=catalog[entry["expression"]])
        entries.append(entry)
    return dict(corpus, entries=entries)
