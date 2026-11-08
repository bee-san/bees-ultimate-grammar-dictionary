"""絵でわかる日本語's illustrated edition: the union with v1.03, and its pictures.

Synthetic rows only; the locked archive is exercised by the corpus build.
"""

from __future__ import annotations

import io
import itertools
import json
import pathlib
import zipfile

import pytest

from bugd.banks import build_term_entry
from bugd.illustrations import with_media
from bugd.jsonio import MalformedPayload
from bugd.pipeline import entry_from_json
from bugd.sources.edewakaru import (
    ILLUSTRATED_ARCHIVE,
    ILLUSTRATED_REVISION,
    EdewakaruExtractor,
    read_illustrated,
    union_rows,
)
from bugd.sources.yomitan_bank import TermRow
from bugd.website import point_page

V6 = f"{ILLUSTRATED_ARCHIVE}:term_bank_1.json"
POST = "〜なりとも｜日本語能力試験\n【意味】\nせめて〜だけでも"


def row(expression: str, text: str, *, images: tuple[str, ...] = (), member: str = "term_bank_1.json",
        definition_tags: str = "") -> TermRow:
    return TermRow(expression=expression, reading=expression, definition_tags=definition_tags,
                   deinflectors="", sequence=0, term_tags="", text=text, images=images, member=member)


def test_v103_rows_come_first_unchanged_and_gain_their_picture() -> None:
    legacy = [row("なりとも", POST), row("せめて", "other post")]
    illustrated = [row("なりとも", POST.replace("\n", "\n\n"), images=("img2/a.jpeg",), member=V6),
                   row("せめて", "other post", images=("img2/b.jpeg",), member=V6)]
    rows = union_rows(legacy, illustrated)
    assert [(r.expression, r.member, r.images) for r in rows] == [
        ("なりとも", "term_bank_1.json", ("img2/a.jpeg",)),
        ("せめて", "term_bank_1.json", ("img2/b.jpeg",)),
    ]
    assert rows[0].text == POST


def test_only_new_posts_and_distinct_pictures_are_appended() -> None:
    legacy = [row("なりとも", POST)]
    illustrated = [
        row("なりとも", POST, images=("img2/a.jpeg",), member=V6),
        row("多少なりとも", POST, images=("img2/a.jpeg",), member=V6),  # a known post, re-filed
        row("大抵", "たいてい｜new post", images=("img2/c.jpeg",), member=V6),
        row("割る", "", images=("img/general.jpeg",), member=V6),
        row("割る", "", images=("img/accident.jpeg",), member=V6, definition_tags="（不注意・失敗）"),
        row("割る", "", images=("img/general.jpeg",), member=V6),  # exact repeat
    ]
    appended = union_rows(legacy, illustrated)[1:]
    assert [(r.expression, r.images) for r in appended] == [
        ("大抵", ("img2/c.jpeg",)),
        ("割る", ("img/general.jpeg",)),
        ("割る", ("img/accident.jpeg",)),
    ]


def test_one_text_with_two_pictures_fails_closed() -> None:
    illustrated = [row("a", POST, images=("img/1.jpeg",), member=V6),
                   row("b", POST, images=("img/2.jpeg",), member=V6)]
    with pytest.raises(MalformedPayload, match="different illustrations"):
        union_rows([row("a", POST)], illustrated)


def _archive(revision: str, rows: list, images: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("index.json", json.dumps({"revision": revision}))
        archive.writestr("term_bank_1.json", json.dumps(rows, ensure_ascii=False))
        archive.writestr("term_bank_2.json", "[]")
        for name in images:
            archive.writestr(name, b"jpeg")
    return buffer.getvalue()


def _bank_row(expression: str, path: str) -> list:
    glossary = [{"type": "structured-content", "content": [{"tag": "img", "path": path}, POST]}]
    return [expression, expression, "", "", 0, glossary, 0, ""]


def test_reading_the_illustrated_archive_checks_revision_and_pictures() -> None:
    rows = read_illustrated(_archive(ILLUSTRATED_REVISION, [_bank_row("なりとも", "img2/a.jpeg")], ["img2/a.jpeg"]))
    assert rows[0].images == ("img2/a.jpeg",) and rows[0].member == V6
    with pytest.raises(MalformedPayload, match="expected revision"):
        read_illustrated(_archive("edewakaru_v7", [], []))
    with pytest.raises(MalformedPayload, match="missing illustration"):
        read_illustrated(_archive(ILLUSTRATED_REVISION, [_bank_row("なりとも", "img2/a.jpeg")], []))


def test_picture_only_post_keeps_its_caption_out_of_the_lookup_forms() -> None:
    extractor = EdewakaruExtractor(pathlib.Path("unused"))
    point = extractor.parse(row("割る", "", images=("img/accident.jpeg",), member=V6,
                                definition_tags="倒れる・倒す①"))
    assert point.variants == ()
    assert point.provenance["illustrationOnly"] is True
    assert point.provenance["attachOnly"] is True
    assert point.provenance["illustrationLabel"] == "倒れる・倒す①"
    assert point.provenance["illustration"] == "img/accident.jpeg"
    legacy = extractor.parse(row("なりとも", POST, images=("img2/a.jpeg",)))
    assert "attachOnly" not in legacy.provenance and legacy.provenance["illustration"] == "img2/a.jpeg"


# --------------------------------------------------------------------------
# Dictionaries and articles render every picture, picture-only records too.
# --------------------------------------------------------------------------


_ORDINALS = itertools.count(1)


def contribution(expression: str, **provenance: object) -> dict:
    return {"source": "edewakaru", "source_id": expression, "row_uid": f"edewakaru:{next(_ORDINALS)}",
            "expression": expression, "variants": [], "reading": None, "meaning": None, "structure": None,
            "nuance": None, "explanation": "説明" if not provenance.get("illustrationOnly") else None,
            "notes": None, "jlpt": None, "examples": [], "tags": [], "ai_generated": {},
            "nuance_ja": None, "explanation_ja": None,
            "provenance": {"sourceLabel": "絵でわかる日本語", **provenance}}


CORPUS = {"sourceLabels": {"edewakaru": "絵でわかる日本語"}, "entries": [
    {"expression": "見る", "variants": [], "contributions": [
        contribution("見る", illustration="img2/a.jpeg"),
        contribution("見る", illustration="img/b.jpeg", illustrationOnly=True, illustrationLabel="（感情）")]},
    {"expression": "割る", "variants": [], "contributions": [
        contribution("割る", illustration="img/c.jpeg", illustrationOnly=True)]},
]}
IMAGES = {f"edewakaru:{path}": {"width": 480, "height": 600,
                                 "website": {"file": f"edewakaru/{name}.jpeg"},
                                 "dictionary": {"file": f"edewakaru/{name}.avif"}}
          for path, name in (("img2/a.jpeg", "a"), ("img/b.jpeg", "b"), ("img/c.jpeg", "c"))}


def _popup(corpus: dict, index: int) -> list:
    return build_term_entry(entry_from_json(corpus["entries"][index]), 1)


def _images(node: object) -> list[dict]:
    if isinstance(node, list):
        return [image for child in node for image in _images(child)]
    if isinstance(node, dict):
        return ([node] if node.get("tag") == "img" else []) + _images(node.get("content"))
    return []


def test_popup_shows_each_picture_at_its_native_size() -> None:
    illustrated = with_media(CORPUS, IMAGES)
    assert "illustrationMedia" not in CORPUS["entries"][0]["contributions"][0]["provenance"]  # input untouched
    images = _images(_popup(illustrated, 0))
    assert [(i["path"], i["width"], i["height"], i["sizeUnits"]) for i in images] == [
        ("media/edewakaru/a.avif", 480, 600, "px"), ("media/edewakaru/b.avif", 480, 600, "px")]
    assert "（感情）" in json.dumps(_popup(illustrated, 0), ensure_ascii=False)  # the caption labels its sense
    assert [i["path"] for i in _images(_popup(illustrated, 1))] == ["media/edewakaru/c.avif"]
    assert _images(_popup(CORPUS, 0)) == []  # no packed media, no picture


def test_article_shows_each_picture_and_no_empty_placeholder() -> None:
    labels = CORPUS["sourceLabels"]
    page = point_page(CORPUS["entries"][1], labels, CORPUS["entries"][1], english=False, figures=IMAGES)
    assert 'src="../../illustrations/edewakaru/c.jpeg"' in page
    assert 'width="480" height="600" loading="lazy"' in page
    assert "without an explanation" not in page
    captioned = point_page(CORPUS["entries"][0], labels, CORPUS["entries"][0], english=True, figures=IMAGES)
    assert 'src="../../../illustrations/edewakaru/b.jpeg"' in captioned
    assert '<figcaption lang="ja">（感情）</figcaption>' in captioned


def test_renditions_keep_the_original_for_the_website_and_compress_for_the_dictionary(tmp_path) -> None:
    pil = pytest.importorskip("PIL.Image")
    picture = io.BytesIO()
    pil.new("RGB", (48, 60), "white").save(picture, "JPEG")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("img/x.jpeg", picture.getvalue())
    from bugd.illustrations import build, load_catalog, write_catalog

    catalog = build(["edewakaru:img/x.jpeg"], {"edewakaru": archive.getvalue()}, tmp_path)
    write_catalog(catalog, tmp_path)
    item = load_catalog(tmp_path)["images"]["edewakaru:img/x.jpeg"]
    assert (item["width"], item["height"]) == (48, 60)
    assert (tmp_path / "illustrations" / item["website"]["file"]).read_bytes() == picture.getvalue()
    assert (tmp_path / "illustrations" / item["dictionary"]["file"]).read_bytes()[4:12] == b"ftypavif"
    # A refresh with unchanged inputs reuses every committed rendition.
    assert build(["edewakaru:img/x.jpeg"], {"edewakaru": archive.getvalue()}, tmp_path, previous=catalog) == catalog


def test_archive_packs_exactly_the_pictures_its_cards_show() -> None:
    from bugd.package import package_members

    card = [{"type": "structured-content", "content": {"tag": "img", "path": "media/edewakaru/a.avif"}}]
    banks = {"term_bank_1.json": [["見る", "みる", "", "", 0, card, 1, ""]]}
    members = package_members(index={}, banks=banks, styles_css="",
                              media={"edewakaru/a.avif": b"a", "edewakaru/unshown.avif": b"b"})
    assert [name for name in members if name.startswith("media/")] == ["media/edewakaru/a.avif"]
    with pytest.raises(MalformedPayload, match="not packed"):
        package_members(index={}, banks=banks, styles_css="", media={})
