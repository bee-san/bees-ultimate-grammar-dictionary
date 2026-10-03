"""AIUEO JLPT Grammar: bilingual grammar notes from the user's Anki export.

The deck repeats each definition on five sentence cards. Group only identical
headword/level/formation/explanation tuples; different senses stay separate.
"""

from __future__ import annotations

from collections import OrderedDict

from ..anki import AnkiNote, read_apkg_notes
from ..jsonio import MalformedPayload
from ..model import Example, GrammarPoint, JLPT_LEVELS
from .base import Extractor, ExtractResult, load_source_lock, write_points_jsonl
from .bunpro import _flatten
from .registry import register_extractor

APKG_NAME = "AIUEO JLPT Grammar.apkg"
NOTETYPE = "Aiueo-Grammar"
REQUIRED_FIELDS = ("GrammarPoint", "JLPTLevel", "Usage", "Description", "SentenceJP", "SentenceEN")


def parse_notes(notes: list[AnkiNote]) -> tuple[list[GrammarPoint], list[int]]:
    groups: OrderedDict[tuple, dict] = OrderedDict()
    skipped: list[int] = []
    for note in notes:
        if any(name not in note.fields for name in REQUIRED_FIELDS):
            raise MalformedPayload(f"aiueo: note {note.note_id} is missing a required field")
        fields = {name: _flatten(note.fields[name]) for name in REQUIRED_FIELDS}
        if fields["GrammarPoint"] == "Grammar Point" and fields["JLPTLevel"] == "JLPT Level":
            skipped.append(note.note_id)
            continue
        expression = fields["GrammarPoint"]
        level = fields["JLPTLevel"]
        if not expression or level not in JLPT_LEVELS or not fields["Description"]:
            raise MalformedPayload(f"aiueo: invalid grammar record on note {note.note_id}")
        japanese, separator, english = fields["Description"].partition("【Translation】")
        key = (expression, level, fields["Usage"], japanese.strip(), english.strip())
        group = groups.setdefault(key, {"ids": [], "examples": [], "tags": []})
        group["ids"].append(note.note_id)
        group["tags"].extend(tag for tag in note.tags if tag not in group["tags"])
        if fields["SentenceJP"]:
            example = Example(japanese=fields["SentenceJP"], english=fields["SentenceEN"])
            if example not in group["examples"]:
                group["examples"].append(example)

    points = []
    for (expression, level, usage, japanese, english), group in groups.items():
        points.append(GrammarPoint(
            source="aiueo", source_id=str(group["ids"][0]), expression=expression,
            jlpt=level, structure=usage, meaning=english or japanese,
            explanation=english or None, explanation_ja=japanese or None,
            examples=tuple(group["examples"]), tags=tuple(group["tags"]),
            provenance={"sourceLabel": "AIUEO JLPT Grammar", "notetype": NOTETYPE,
                        "noteIds": group["ids"]},
        ))
    return points, skipped


@register_extractor
class AiueoExtractor(Extractor):
    name = "aiueo"
    label = "AIUEO JLPT Grammar"

    def extract(self) -> ExtractResult:
        lock = load_source_lock(self.input_dir)
        if APKG_NAME not in lock:
            raise MalformedPayload(f"aiueo: locked input is missing: {APKG_NAME}")
        notes = read_apkg_notes(self.read_locked_bytes(APKG_NAME), notetype=NOTETYPE)
        points, skipped = parse_notes(notes)
        write_points_jsonl(self.input_dir, points)
        return ExtractResult(
            source=self.name, points=points, consumed={APKG_NAME: lock[APKG_NAME]["sha256"]},
            stats={"notes": len(notes), "points": len(points), "skippedHeaderNotes": skipped,
                   "examples": sum(len(point.examples) for point in points), "notetype": NOTETYPE},
        )
