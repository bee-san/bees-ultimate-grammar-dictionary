from __future__ import annotations

import gzip
import json
import pathlib

import pytest

from bugd.imabi_lookup import apply_lookups, load_catalog, restore_lessons
from bugd.inflection import inflection_rules
from bugd.popup_lookup import (
    apply_popup_lookups, identity, is_japanese_form, literal_forms, load_overrides, lookup_plan,
)
from bugd.readings import is_exact_reading
from bugd.website import grouped_entries

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def indexed():
    base = json.loads(gzip.decompress((ROOT / "website/data/corpus.json.gz").read_bytes()))
    base = restore_lessons(base, ROOT / "data/sources/imabi", ["535"])
    before = apply_lookups(base, load_catalog())
    return before, apply_popup_lookups(before)


@pytest.mark.parametrize("title,expected", [
    ("Nらしい", ["らしい"]), ("AながらB", ["ながら"]),
    ("Verb[て]", ["て"]), ("Number/Amount + は", ["は"]),
    ("ば〜ほど", ["ほど"]), ("NからNにかけて", ["にかけて"]),
    ("たり...たり", ["たり"]), ("〜に対して", ["に対して"]),
    ("ている①", ["ている"]), ("の（だろう）か", ["のか", "のだろうか"]),
    ("でもあり、でもある", ["でもあり", "でもある"]),
    ("だに + しない", ["だにしない"]),
    ("English lesson title", []),
])
def test_notation_becomes_real_surface_forms(title, expected):
    assert literal_forms(title) == expected


def test_every_source_record_has_a_japanese_lookup_and_retains_original_content(indexed):
    before, after = indexed
    plan = lookup_plan(before, load_overrides())
    assert len(plan) == 9152
    grouped = grouped_entries(after)
    present = {form: {identity(p) for p in row["contributions"]}
               for form, row in grouped.items() if is_japanese_form(form)}
    for key, item in plan.items():
        assert item["forms"], key
        for form in item["forms"]:
            assert key in present[form], (key, form)
    assert set(before["sourceLabels"]) == {source for source, _ in plan}
    for old, new in zip(before["entries"], after["entries"]):
        assert old["expression"] == new["expression"]
        assert old["variants"] == new["variants"]
        assert old["contributions"] == new["contributions"][:len(old["contributions"])]
    assert apply_popup_lookups(after) == after


@pytest.mark.parametrize("row_uid,form", [
    ("bunpro:245", "ないで"), ("bunpro:175", "ましょう"),
    ("bunpro:227", "させる"), ("bunpro:146", "られる"),
    ("bunpro:59", "なかった"), ("bunpro:46", "ました"),
    ("donna_toki:465", "てはかなわない"), ("donna_toki:537", "といったらない"),
    ("donna_toki:558", "どころではない"), ("aiueo:571", "に負うところが大きい"),
    ("edewakaru:93", "のも無理はない"),
])
def test_ambiguous_headwords_use_their_own_source_construction(indexed, row_uid, form):
    _, corpus = indexed
    assert any(p.get("row_uid") == row_uid for e in corpus["entries"]
               if e["expression"] == form for p in e["contributions"])


def test_generic_verb_titles_do_not_assign_unrelated_senses_to_te(indexed):
    _, corpus = indexed
    ids = {p.get("row_uid") for e in corpus["entries"] if e["expression"] == "て"
           for p in e["contributions"]}
    assert {"bunpro:245", "bunpro:175", "bunpro:227", "bunpro:146"}.isdisjoint(ids)


@pytest.mark.parametrize("written,reading,expected", [
    ("に対して", "にたいして", True), ("ざるを得ない", "ざるをえない", True),
    ("間に", "あいだに", True), ("癖に", "くせにくせして", False),
    ("直す", "す", False), ("際に", "さい", False),
    ("うと思う", "ようとおもう", False), ("結構", "けっか", False),
])
def test_reading_aliases_require_the_whole_written_form(written, reading, expected):
    assert is_exact_reading(written, reading) is expected


def test_alias_does_not_inherit_a_discontinuous_pattern_reading(indexed):
    _, corpus = indexed
    for row in corpus["entries"]:
        for point in row["contributions"]:
            if point.get("provenance", {}).get("popupLookupRow"):
                assert point["reading"] is None


def test_missing_forms_and_changed_override_evidence_block_publication():
    corpus = {"sourceLabels": {"test": "Test"}, "entries": [
        {"expression": "Unknown English title", "contributions": [
            {"source": "test", "source_id": "1", "row_uid": "test:1", "expression": "Unknown English title"}]}]}
    with pytest.raises(ValueError, match="need Japanese popup lookups"):
        apply_popup_lookups(corpus, {})
    assert apply_popup_lookups(corpus, {}, require_coverage=False) == corpus
    override = {("test", "test:1"): {"sourceId": "different", "forms": ["は"]}}
    with pytest.raises(ValueError, match="Stale popup override"):
        apply_popup_lookups(corpus, override)


@pytest.mark.parametrize("form,rules", [
    ("てしまう", "v5"), ("すぎる", "v1"), ("出来る", "v1"),
    ("てくる", "vk"), ("にくい", "adj-i"), ("ことにする", "vs"),
    ("に違いない", "adj-i"), ("いる", "v1 v5"),
    ("を", ""), ("かい", ""), ("くらい", ""), ("に対して", ""),
    ("とにかく", ""), ("ともかく", ""), ("に足りる", "v1"), ("に基づく", "v5"),
    ("English title", ""), ("Nらしい", ""),
])
def test_conjugation_classes_are_limited_to_known_literal_endings(form, rules):
    assert inflection_rules(form) == rules
