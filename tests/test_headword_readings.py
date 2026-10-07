from __future__ import annotations

import json

import pytest

from bugd.banks import build_term_entry
from bugd.headword_readings import apply_catalog, load_catalog, needs_reading
from bugd.merge import MergedEntry
from bugd.model import GrammarPoint
from bugd.pipeline import entry_from_json
from bugd.readings import is_exact_reading


def _entry(expression, reading=None, **extra):
    point = {"source": "imabi", "source_id": "1", "row_uid": "imabi:1", "expression": expression, "reading": reading}
    return {"expression": expression, "variants": [], "contributions": [point], **extra}


def test_committed_catalog_spells_every_headword_and_survives_the_gate():
    catalog = load_catalog()
    assert len(catalog) > 600
    assert all(is_exact_reading(expression, reading) for expression, reading in catalog.items())
    # Counters take their counter reading, not the context-free noun reading.
    assert catalog["本"] == "ほん" and catalog["頭"] == "とう" and catalog["的"] == "てき"
    # A reading that would also match an unrelated particle is left out.
    assert "化" not in catalog and "杯" not in catalog


def test_a_catalog_reading_fills_only_headwords_without_an_exact_source_reading():
    corpus = {"entries": [_entry("その上"), _entry("に向けて", "にむけて"), _entry("ずにはいる", lookup=False),
                          _entry("と", "と～ない")]}
    catalog = {"その上": "そのうえ", "に向けて": "にむけ", "ずにはいる": "ずにはいられない"}
    rows = {e["expression"]: e for e in apply_catalog(corpus, catalog)["entries"]}
    assert rows["その上"]["reading"] == "そのうえ"
    assert "reading" not in rows["に向けて"]       # the source's exact reading wins
    assert "reading" not in rows["ずにはいる"]     # compatibility rows stay unreachable
    assert not needs_reading(rows["と"])          # kana needs no reading
    built = build_term_entry(entry_from_json(rows["その上"]), 1)
    assert built[1] == "そのうえ"


def test_the_catalog_refuses_a_reading_that_does_not_spell_its_headword(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schemaVersion": 1, "records": {"に向け": {"reading": "にむけて"}}}))
    with pytest.raises(ValueError, match="does not spell"):
        load_catalog(path)


def test_an_entry_reading_never_overrides_an_exact_source_reading():
    point = GrammarPoint(source="dojg", source_id="1", expression="上", reading="うえ")
    entry = MergedEntry(expression="上", contributions=[point], reading="じょう")
    assert build_term_entry(entry, 1)[1] == "うえ"


@pytest.mark.parametrize("written,reading,expected", [
    ("ヶ月", "かげつ", True), ("ヵ所", "かしょ", True), ("ヶ月", "けげつ", False),
    ("各々", "おのおの", True), ("所以", "ゆえん", True), ("当って", "あたって", True),
])
def test_counter_abbreviations_and_whole_words_pass_the_exact_gate(written, reading, expected):
    assert is_exact_reading(written, reading) is expected
