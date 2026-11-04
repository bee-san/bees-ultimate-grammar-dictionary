from __future__ import annotations

import json
import pathlib

import pytest

from bugd.jsonio import MalformedPayload
from bugd.pipeline import point_from_json
from bugd.sources.kurabete import ARCHIVE_NAME, KurabeteExtractor, parse_body, parse_rows

SOURCE_DIR = pathlib.Path(__file__).resolve().parents[1] / "data" / "sources" / "kurabete"

CIRCLE = {"tag": "span", "data": {"class": "icon"}, "content": [
    {"tag": "span", "data": {"class": "image"}, "content": {"tag": "img", "path": "image/circle-regular.svg"}}]}
CROSS = {"tag": "span", "data": {"class": "icon"}, "content": [
    {"tag": "span", "data": {"class": "image"}, "content": {"tag": "img", "path": "image/xmark-solid.svg"}}]}


def div(cls, *content):
    return {"tag": "div", "data": {"class": cls}, "content": list(content)}


def span(cls, *content):
    return {"tag": "span", "data": {"class": cls}, "content": list(content)}


def tag(label):
    return span("tag", div("tag__inner", label))


def judged(icon, text):
    return div("correct" if icon is CIRCLE else "wrong", icon, span("text", text))


def body(number="1", *, sections=None):
    sections = sections if sections is not None else [
        div("meaning", tag("意味1"), span("text", "Ａがエスカレートした。")),
        div("examples", tag("例文1"), div("examples__inner",
            div("example", div("list_number", "①"), span("text", "悩み抜いたあげく、決断した。")))),
        div("notes", tag("注意1"), div("notes__inner", div("note",
            div("explanation", "・副詞的な使い方。"),
            judged(CIRCLE, "あげくの果てに家をなくした。")))),
        div("comparisons", tag("対比1"), div("comparisons_inner", div("comparison",
            div("synonym", "「Ａた末Ｂ」（意味1 P.117）"),
            judged(CIRCLE, "手術を繰り返した末、健康になった。"),
            judged(CROSS, "手術を繰り返したあげく、健康になった。")))),
        div("usages", tag("接続1"), div("usages_inner",
            div("usage", span("notation new", "［イ形－", span("linethrough", "い"), "］かろうが")),
            {"tag": "details", "data": {"class": "original-notation"}, "content": [
                {"tag": "summary", "content": "原書の接続表記"},
                div("original-line", span("notation origin", "［イ形容詞⑥］かろうが"))]})),
    ]
    root = {"tag": "div", "data": {"root": "kurabe"}, "content": [{"tag": "div", "content": [
        div("number", number),
        div("grammar", div("divider_wrapper",
            div("headword", "Ａ", span("place_holder", "　"), "あげく", span("place_holder", "　"), "Ｂ"),
            div("derivations", span("derivation", "ＡあげくにＢ")))),
        *sections,
    ]}]}
    return [{"type": "structured-content", "content": root}]


def row(expression, sequence, glossary, *, reading="", tag_name="文型"):
    return ("term_bank_1.json", [expression, reading, tag_name, "", 0, glossary, sequence, ""])


def test_body_keeps_every_section_with_judgement_marks():
    parsed = parse_body(body())
    assert parsed["meaning"] == "Ａがエスカレートした。"
    assert [example.japanese for example in parsed["examples"]] == ["悩み抜いたあげく、決断した。"]
    # The judged sentence inside a note is its own line, not glued to the prose.
    assert parsed["notes"] == "【注意1】\n・副詞的な使い方。\n○あげくの果てに家をなくした。"
    assert parsed["explanation"] == (
        "【対比1】\n\n「Ａた末Ｂ」（意味1 P.117）\n"
        "○手術を繰り返した末、健康になった。\n×手術を繰り返したあげく、健康になった。"
    )
    assert parsed["structure"] == "ＡあげくＢ（ＡあげくにＢ）\n［イ形－<s>い</s>］かろうが"
    assert parsed["originalNotation"] == ["［イ形容詞⑥］かろうが"]


def test_stacked_alternatives_and_subscripts_survive_flattening():
    multiline = span("text", div("multiline_side", "給料"),
        div("multiline_bracket three", span("image", {"tag": "img", "path": "image/bracket_left.svg"})),
        div("multiline", div("line", judged(CIRCLE, "からいうと")), div("line", judged(CROSS, "からすると"))),
        div("multiline_bracket three", span("image", {"tag": "img", "path": "image/bracket_right.svg"})),
        div("multiline_side", "同額だ。"))
    parsed = parse_body(body(sections=[
        div("meaning", tag("意味1"), span("text", "Ａ", span("sub", "1"), "を希望する。")),
        div("comparisons", tag("対比1"), div("comparisons_inner", div("comparison", div("correct", CIRCLE, multiline)))),
    ]))
    assert parsed["meaning"] == "Ａ₁を希望する。"
    assert parsed["explanation"].endswith("○給料｛○からいうと／×からすると｝同額だ。")


def test_rows_group_by_sequence_and_front_matter_is_skipped():
    glossary = body()
    points, stats = parse_rows([
        row("あげくに", 1, glossary),
        row("あげく", 1, glossary),
        row("挙げ句", 1, glossary, reading="あげく"),
        row("くらべてわかる日本語表現文型辞典", 2, [], tag_name="資料"),
    ])
    assert stats["frontMatterRows"] == 1
    (point,) = points
    # The spelling matching the printed headword (Ａ あげく Ｂ) is canonical.
    assert point.expression == "あげく"
    assert point.variants == ("あげくに", "挙げ句")
    assert point.provenance["lookupForms"][2] == {"expression": "挙げ句", "reading": "あげく"}


def test_differing_bodies_or_unknown_blocks_fail_closed():
    with pytest.raises(MalformedPayload):
        parse_rows([row("あげく", 1, body()), row("あげくに", 1, body(sections=[
            div("meaning", tag("意味1"), span("text", "別。"))]))])
    with pytest.raises(MalformedPayload):
        parse_body(body(sections=[div("meaning", tag("意味1"), span("text", "Ａ")), div("mystery", "x")]))
    with pytest.raises(MalformedPayload):
        parse_rows([row("あげく", 2, body(number="1"))])


@pytest.mark.skipif(not (SOURCE_DIR / ARCHIVE_NAME).is_file(), reason="local Kurabete archive not acquired")
def test_locked_real_archive_conserves_every_pattern_and_lookup_row():
    result = KurabeteExtractor(SOURCE_DIR).extract()
    assert result.stats["termRows"] == 1071
    assert result.stats["frontMatterRows"] == 1
    assert len(result.points) == 363
    assert result.stats["lookupForms"] == 1070
    assert all(point.meaning and point.structure for point in result.points)
    sidecar = [point_from_json(json.loads(line)) for line in (SOURCE_DIR / "points.jsonl").read_text().splitlines()]
    assert sidecar == result.points


def test_english_edition_keeps_judged_japanese_sentences():
    from bugd.english import restore_judged_sentences

    original = "説明。\n○勉強した結果、合格した。\n×勉強したあげく、合格した。"
    translated = "Explanation.\n○After studying, I passed.\n×After studying using あげく, I passed."
    assert restore_judged_sentences(original, translated) == (
        "Explanation.\n○勉強した結果、合格した。 — After studying, I passed.\n"
        "×勉強したあげく、合格した。 — After studying using あげく, I passed."
    )
    # Unaligned output is left as Luna returned it rather than mispaired.
    assert restore_judged_sentences(original, "○One line only.") == "○One line only."
