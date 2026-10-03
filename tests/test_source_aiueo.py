from __future__ import annotations

import json
import pathlib

import pytest

from bugd.anki import AnkiNote
from bugd.jsonio import MalformedPayload
from bugd.pipeline import point_from_json
from bugd.sources.aiueo import APKG_NAME, AiueoExtractor, parse_notes

SOURCE_DIR = pathlib.Path(__file__).resolve().parents[1] / "data" / "sources" / "aiueo"


def note(identifier, sentence, *, description='日本語の説明。<br>【Translation】An English explanation.', level='N4'):
    return AnkiNote(note_id=identifier, notetype='Aiueo-Grammar', tags=(), fields={
        'GrammarPoint': 'ながら', 'JLPTLevel': level, 'Usage': '動詞ます形＋ながら',
        'Description': description, 'SentenceJP': sentence, 'SentenceEN': 'While reading.',
    })


def test_sentence_cards_merge_without_erasing_distinct_senses():
    points, skipped = parse_notes([
        note(1, '本を読みながら。'), note(2, '音楽を聞きながら。'),
        note(3, '知りながら。', description='逆接。<br>【Translation】Although.', level='N2'),
    ])
    assert not skipped
    assert len(points) == 2
    assert len(points[0].examples) == 2
    assert points[0].explanation == 'An English explanation.'
    assert points[0].explanation_ja == '日本語の説明。'
    assert points[0].provenance['noteIds'] == [1, 2]
    assert points[1].jlpt == 'N2'


def test_html_entities_do_not_create_duplicate_definitions():
    points, _ = parse_notes([
        note(1, '一。', description='説明。<br>【Translation】Use &quot;while&quot;.'),
        note(2, '二。', description='説明。<br>【Translation】Use "while".'),
    ])
    assert len(points) == 1
    assert len(points[0].examples) == 2


def test_bad_record_fails_instead_of_silently_dropping_a_definition():
    with pytest.raises(MalformedPayload):
        parse_notes([note(1, '例。', level='unknown')])


@pytest.mark.skipif(not (SOURCE_DIR / APKG_NAME).is_file(), reason='local AIUEO export not acquired')
def test_locked_real_deck_conserves_all_grammar_and_sentence_notes():
    result = AiueoExtractor(SOURCE_DIR).extract()
    assert result.stats['notes'] == 3806
    assert len(result.stats['skippedHeaderNotes']) == 1
    assert len(result.points) == 761
    assert sum(len(point.examples) for point in result.points) == 3805
    assert all(len(point.examples) == 5 for point in result.points)
    assert {point.jlpt for point in result.points} == {'N1', 'N2', 'N3', 'N4', 'N5'}
    assert all(point.explanation and point.explanation_ja for point in result.points)
    sidecar = [point_from_json(json.loads(line)) for line in (SOURCE_DIR / 'points.jsonl').read_text().splitlines()]
    assert sidecar == result.points
