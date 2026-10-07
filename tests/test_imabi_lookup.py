from __future__ import annotations

import copy
import gzip
import json
import pathlib

import pytest

from bugd.banks import build_term_entry
from bugd.imabi_lookup import apply_lookups, load_catalog
from bugd.pipeline import entry_from_json, point_to_json
from bugd.sources.imabi import ImabiExtractor
from bugd.unify import build_contribution, to_grammar_point
from bugd.website import grouped_entries, point_page

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def publication():
    baseline = json.loads(gzip.decompress((ROOT / "website/data/corpus.json.gz").read_bytes()))
    return baseline, apply_lookups(baseline, load_catalog())


@pytest.mark.parametrize("expression,page_ids", [
    ("は", {"85"}), ("が", {"83", "103", "243"}), ("を", {"91", "9840"}),
    ("に", {"139", "161", "352", "992", "3526", "3561", "4399", "4429"}),
    ("へ", {"141"}), ("で", {"143", "273"}), ("の", {"137", "271", "314"}),
    ("と", {"159", "221", "336", "9543"}), ("も", {"105", "263", "340"}),
    ("から", {"181", "203"}), ("まで", {"183", "744"}), ("より", {"444"}),
    ("か", {"99", "101", "167"}), ("よ", {"245"}), ("ね", {"245"}),
    ("だけ", {"261"}), ("しか", {"334"}), ("ばかり", {"751"}),
    ("ので", {"203"}), ("のに", {"205"}), ("けど", {"243"}),
    ("けれども", {"243"}), ("ぐらい", {"442"}), ("なら", {"336"}),
    ("のだ", {"7485", "9904"}), ("んだ", {"7485", "9904"}),
    ("にくい", {"328"}), ("ざるを得ない", {"627"}), ("やむを得ない", {"627"}),
    ("てある", {"151", "539"}), ("込む", {"773"}),
])
def test_exact_japanese_lookup_finds_relevant_lessons(publication, expression, page_ids):
    _, corpus = publication
    actual = {p["source_id"] for e in corpus["entries"] if e["expression"] == expression
              for p in e["contributions"] if p["source"] == "imabi"}
    assert page_ids <= actual


def test_every_catalog_link_is_present_once_and_no_original_entry_is_removed(publication):
    baseline, corpus = publication
    by_expression = {}
    for entry in corpus["entries"]:
        by_expression.setdefault(entry["expression"], []).extend(entry["contributions"])
    for page_id, lesson in load_catalog().items():
        for expression in lesson["expressions"]:
            assert sum(p["source"] == "imabi" and p["source_id"] == page_id
                       for p in by_expression[expression]) == 1
    assert {e["expression"] for e in baseline["entries"]} <= set(by_expression)
    # Indexing is additive: every original entry remains in place, with all
    # original substance and source identities, including other dictionaries.
    for before, after in zip(baseline["entries"], corpus["entries"]):
        assert before["expression"] == after["expression"]
        assert before["variants"] == after["variants"]
        for old, new in zip(before["contributions"], after["contributions"]):
            if old["source"] != "imabi":
                assert old == new
            else:
                assert {k: v for k, v in old.items() if k != "provenance"} == {
                    k: v for k, v in new.items() if k != "provenance"}
                assert old["provenance"].items() <= new["provenance"].items()


def test_indexing_is_idempotent_and_does_not_mutate_input(publication):
    baseline, corpus = publication
    assert not any("lookupExpressions" in p.get("provenance", {})
                   for e in baseline["entries"] for p in e["contributions"])
    assert apply_lookups(corpus, load_catalog()) == corpus


def test_missing_lessons_fail_closed():
    with pytest.raises(ValueError, match="Missing IMABI lookup lessons"):
        apply_lookups({"entries": []}, load_catalog())


def test_named_patterns_are_not_split_into_incidental_particles(publication):
    _, corpus = publication
    for expression in ("ざる", "を", "ない"):
        assert not any(p["source"] == "imabi" and p["source_id"] == "627"
                       for e in corpus["entries"] if e["expression"] == expression
                       for p in e["contributions"])


def test_acquired_source_build_carries_the_same_lookup_links():
    points = ImabiExtractor(ROOT / "data/sources/imabi").extract().points
    point = next(p for p in points if p.source_id == "85")
    contribution = build_contribution("imabi", point_to_json(point),
                                      canonical_key=point.expression, source_label="IMABI")
    restored = to_grammar_point(contribution, expression=point.expression)
    assert restored.provenance["lookupExpressions"] == ["は"]
    assert restored.provenance["lessonTitle"] == point.expression
    extracted = {"sourceLabels": {"imabi": "IMABI"}, "entries": [
        {"expression": p.expression, "variants": [], "contributions": [point_to_json(p)]}
        for p in points]}
    indexed = apply_lookups(extracted)
    for page_id, lesson in load_catalog().items():
        for expression in lesson["expressions"]:
            assert any(p["source_id"] == page_id for e in indexed["entries"]
                       if e["expression"] == expression for p in e["contributions"])


def test_multiple_lessons_keep_titles_and_full_content_on_article(publication):
    _, corpus = publication
    entry = grouped_entries(corpus)["のだ"]
    points = [p for p in entry["contributions"] if p["source"] == "imabi"]
    assert {p["source_id"] for p in points} == {"7485", "9904"}
    page = point_page(entry, corpus["sourceLabels"], entry, english=False)
    row = build_term_entry(entry_from_json(entry), 1)
    packed = json.dumps(row, ensure_ascii=False)
    for title in ("The Scope Marker ～のだ", "The Mood Marker ～のだ"):
        assert title in page
        assert title in packed


def test_redirect_and_real_lesson_at_same_spelling_keep_both_sources():
    other = {"source": "other", "source_id": "1", "row_uid": "other:1", "explanation": "Original."}
    imabi = {"source": "imabi", "source_id": "85", "row_uid": "imabi:14", "explanation": "Lesson."}
    corpus = {"entries": [
        {"expression": "〜は", "contributions": [other]},
        {"expression": "は", "contributions": [{"source": "declared", "source_id": "alias",
                                                   "provenance": {"aliasOf": "〜は"}}]},
        {"expression": "は", "contributions": [imabi, copy.deepcopy(other)]},
    ]}
    resolved = grouped_entries(corpus)["は"]
    assert resolved["contributions"] == [other, imabi]
    assert not resolved["alias"]
