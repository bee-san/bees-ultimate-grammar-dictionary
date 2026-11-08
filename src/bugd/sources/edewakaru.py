"""絵でわかる日本語 — E de wakaru.

Source: `aiko-tanaka/Grammar-Dictionaries` `edewakaru/`, revision
`edewakaru_v1.03;2022-09-01`, 1248 entries across four banks. Structured-content
entries laid out as:

    〜なりとも｜日本語能力試験　JLPT　N１文法
    【接続】 ...
    【意味】 ...
    【例文】 ①sentence  →rephrasing
    【説明】 ...

The producer's distinctive feature is that example sentences are followed by a
`→` rephrasing in plainer Japanese. Those rephrasings are the pedagogical point
of this source, so they are kept with their sentence rather than discarded or
mistaken for separate examples.

Two locked editions are read:

* the text-only v1.03 banks, which built every published release so far, and
* Salwynn's illustrated build (`edewakaru_v6.zip`, revision
  `edewakaru_v6 2024-11-30`), listed in MarvNC's yomitan-dictionaries
  collection. It repeats the v1.03 text verbatim, adds the post's illustration
  to every row, and adds the producer's 自動詞・他動詞 series, whose posts are
  pictures with no text at all.

The v1.03 rows are emitted first, unchanged and in their original order, so
each keeps its `row_uid`, headword and article. Each gains the illustration of
the v6 row with the same text. v6 rows whose text v1.03 already has are not
emitted again: measured, all four such rows (`大抵`, `拍子に`, `拍子で`, `弾みで`)
re-file an existing post under another headword, and would show it twice. The
remaining v6 rows are appended, marked `attachOnly` so they join the finished
alignment without moving any existing contribution (see
`bugd.keymap.attach_late_rows`). A row with an illustration and no text is
marked `illustrationOnly`: it has nothing to show in a text dictionary.
"""

from __future__ import annotations

import dataclasses
import io
import re
import zipfile

from ..jsonio import MalformedPayload, load_json
from ..model import Example, GrammarPoint
from .base import load_source_lock
from .community import (
    CommunityBankExtractor,
    clean,
    jlpt_from_tags,
    split_sections,
)
from .registry import register_extractor
from .yomitan_bank import TermRow, read_term_bank

#: Salwynn's illustrated edition, locked beside the v1.03 banks.
ILLUSTRATED_ARCHIVE = "edewakaru_v6.zip"
#: Producer revision the union below was measured against. A different archive
#: must be reviewed (and this pin moved) before it can be extracted.
ILLUSTRATED_REVISION = "edewakaru_v6 2024-11-30"
ILLUSTRATED_MEMBERS = ("term_bank_1.json", "term_bank_2.json")
_WHITESPACE = re.compile(r"\s+")
from .yomitan_bank import TermRow

_HEADINGS = {
    "接続": "structure",
    "意味": "meaning",
    "例文": "examples",
    "基本例文": "examples",
    "説明": "explanation",
    "使う時": "usage",
    "注意": "notes",
    "口語形": "colloquial",
}

#: The producer numbers examples with circled digits.
_CIRCLED = re.compile(r"^[\s　]*[①-⑳❶-❿][\s　.．、]*")
#: A plainer-Japanese restatement of the preceding sentence.
_REPHRASING = re.compile(r"^[\s　]*[→⇒][\s　]*")
_TITLE_LEVEL = re.compile(r"JLPT[\s　]*([NＮ][\s　]*[1-5１-５])")
#: Blog-ring footer and end-of-post marker the producer appends to every post.
#: Measured over the source: 2,246 `にほんブログ村` lines, 1,057 `――以上――`
#: lines and 492 `語学(日本語)ランキング` lines were shipping as dictionary
#: content, ending each explanation with repeated link captions. They are site
#: chrome, not lexicographic content. `語学(日本語)ランキング` was found by the
#: UGD-14 round-6 visual gate and occurs in exactly that one form, always as its
#: own line, so an exact-line match cannot swallow real prose.
_POST_CHROME = frozenset({
    "にほんブログ村",
    "――以上――",
    "ーー以上ーー",
    "--以上--",
    "語学(日本語)ランキング",
    "語学（日本語）ランキング",
})

#: The same markers, matched as a TRAILING RUN rather than a whole line.
#:
#: The exact-line rule above cannot see a marker the producer concatenated onto
#: the end of a sentence with no newline, and 4 such leaks reached the packaged
#: banks (`だって`, `なんで`, `みたいな`, `みたいに`). Measured over the source the
#: glued form is bounded and always a TAIL: 14 trailing `――以上――`, 2 trailing
#: `にほんブログ村`, and 13 occurrences inside a repeated tail run such as
#: `…語学(日本語)ランキングにほんブログ村にほんブログ村にほんブログ村――以上――`.
#:
#: Anchored at end-of-line and allowed to repeat, so the whole run goes in one
#: pass. Deliberately NOT a free-floating substring match: these captions could
#: legitimately be quoted mid-sentence, and only a tail is provably chrome.
_TRAILING_CHROME = re.compile(
    "(?:" + "|".join(re.escape(marker) for marker in sorted(_POST_CHROME)) + r"|[\s　])+$"
)


def _strip_post_chrome(body: str | None) -> str | None:
    """Drop the producer's blog-ring footer from a prose block.

    Handles both forms the source uses: the marker as its own line, and a run of
    markers glued onto the end of real content.
    """
    if not body:
        return body
    kept = []
    for line in body.split("\n"):
        if line.strip() in _POST_CHROME:
            continue
        # Only strip when the tail actually contains a marker, so an ordinary
        # line merely ending in whitespace is left byte-identical.
        candidate = _TRAILING_CHROME.sub("", line)
        if candidate != line and any(marker in line for marker in _POST_CHROME):
            line = candidate
        kept.append(line)
    return "\n".join(kept)


@register_extractor
class EdewakaruExtractor(CommunityBankExtractor):
    name = "edewakaru"
    label = "絵でわかる日本語"
    members = tuple(f"term_bank_{index}.json" for index in range(1, 5))

    def read_rows(self) -> tuple[list[TermRow], dict[str, str]]:
        legacy, consumed = super().read_rows()
        raw = self.read_locked_bytes(ILLUSTRATED_ARCHIVE)
        consumed[ILLUSTRATED_ARCHIVE] = load_source_lock(self.input_dir)[ILLUSTRATED_ARCHIVE]["sha256"]
        return union_rows(legacy, read_illustrated(raw)), consumed

    def parse(self, row: TermRow) -> GrammarPoint | None:
        illustrated = row.member.startswith(f"{ILLUSTRATED_ARCHIVE}:")
        if illustrated and not body_key(row):
            return self._illustration_only(row)
        sections = split_sections(row.text, _HEADINGS)

        # The level appears in the entry's own title line (`…｜JLPT　N１文法`);
        # the term tag names the producer's difficulty band (初級/中級/上級), which
        # is not a JLPT level and must not be coerced into one.
        title_line = row.text.split("\n", 1)[0]
        level_match = _TITLE_LEVEL.search(title_line) or _TITLE_LEVEL.search(row.text)
        jlpt = jlpt_from_tags(level_match.group(1) if level_match else "")

        provenance = self.base_provenance(row)
        provenance["producerBand"] = row.term_tags
        for optional in ("usage", "notes", "colloquial"):
            if optional in sections:
                provenance[optional] = clean(_strip_post_chrome(sections[optional]))
        if row.images:
            provenance["illustration"] = row.images[0]
        if illustrated:
            provenance["attachOnly"] = True

        return GrammarPoint(
            source=self.name,
            source_id=str(row.sequence) if row.sequence else row.expression,
            expression=row.expression,
            variants=row.variants,
            reading=clean(row.reading),
            meaning=clean(_strip_post_chrome(sections.get("meaning"))),
            structure=clean(_strip_post_chrome(sections.get("structure"))),
            explanation=clean(_strip_post_chrome(sections.get("explanation"))),
            jlpt=jlpt,
            examples=_numbered_examples(
                _strip_post_chrome(sections.get("examples")), row.highlights
            ),
            tags=(row.term_tags,) if row.term_tags else (),
            provenance=provenance,
        )

    def _illustration_only(self, row: TermRow) -> GrammarPoint:
        """A post that is only a picture: the 自動詞・他動詞 series.

        Its `definitionTags` hold a sense label for the picture (`（不注意・失敗）`,
        `倒れる・倒す①`), not alternative spellings, so they are kept as the
        caption and never become lookup forms.
        """
        provenance = self.base_provenance(row)
        provenance["producerBand"] = row.term_tags
        provenance["illustration"] = row.images[0]
        provenance["attachOnly"] = True
        provenance["illustrationOnly"] = True
        if row.definition_tags.strip():
            provenance["illustrationLabel"] = row.definition_tags.strip()
        return GrammarPoint(
            source=self.name,
            source_id=str(row.sequence) if row.sequence else row.expression,
            expression=row.expression,
            reading=clean(row.reading),
            tags=(row.term_tags,) if row.term_tags else (),
            provenance=provenance,
        )


def body_key(row: TermRow) -> str:
    """A row's text with all whitespace removed: both editions' identity for it."""
    return _WHITESPACE.sub("", row.text)


def read_illustrated(raw: bytes) -> list[TermRow]:
    """Read the illustrated edition's banks, failing closed on drift.

    Every row must carry exactly one illustration and every illustration must be
    a member of the archive, so a later build can always resolve it.
    """
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        index = load_json(archive.read("index.json").decode("utf-8"))
        if index.get("revision") != ILLUSTRATED_REVISION:
            raise MalformedPayload(
                f"{ILLUSTRATED_ARCHIVE}: expected revision {ILLUSTRATED_REVISION!r}, "
                f"found {index.get('revision')!r}"
            )
        names = set(archive.namelist())
        rows: list[TermRow] = []
        for member in ILLUSTRATED_MEMBERS:
            rows.extend(read_term_bank(archive.read(member), member=f"{ILLUSTRATED_ARCHIVE}:{member}"))
    for row in rows:
        if len(row.images) != 1:
            raise MalformedPayload(
                f"{row.member}: {row.expression!r} has {len(row.images)} illustrations, expected 1"
            )
        if row.images[0] not in names:
            raise MalformedPayload(f"{row.member}: missing illustration {row.images[0]!r}")
    return rows


def union_rows(legacy: list[TermRow], illustrated: list[TermRow]) -> list[TermRow]:
    """v1.03 rows with their illustrations, then the rows only v6 has.

    A v1.03 row takes the illustration of the v6 row with the same text, keyed
    first by headword and text, then by text alone; one text never carries two
    different pictures in v6. A v6 row is appended only when v1.03 has no row
    with its text. A picture-only row is identified by its headword and picture,
    because several verbs have more than one (割る: a general and an accidental
    sense).
    """
    by_pair: dict[tuple[str, str], tuple[str, ...]] = {}
    by_body: dict[str, set[tuple[str, ...]]] = {}
    for row in illustrated:
        key = body_key(row)
        if key:
            by_pair.setdefault((row.expression, key), row.images)
            by_body.setdefault(key, set()).add(row.images)
    conflicting = [key for key, pictures in by_body.items() if len(pictures) > 1]
    if conflicting:
        raise MalformedPayload(
            f"{ILLUSTRATED_ARCHIVE}: {len(conflicting)} texts carry different illustrations"
        )

    rows: list[TermRow] = []
    legacy_texts: set[str] = set()
    for row in legacy:
        key = body_key(row)
        if not key:
            raise MalformedPayload(f"{row.member}: {row.expression!r} has no text")
        pictures = by_pair.get((row.expression, key)) or next(iter(by_body.get(key, ())), ())
        rows.append(dataclasses.replace(row, images=pictures))
        legacy_texts.add(key)
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for row in illustrated:
        key = body_key(row)
        if key in legacy_texts:
            continue
        identity = (row.expression, key, () if key else row.images)
        if identity in seen:
            continue
        seen.add(identity)
        rows.append(row)
    return rows


def _numbered_examples(
    body: str | None, highlights: tuple[str, ...]
) -> tuple[Example, ...]:
    """Collect circled-digit examples, keeping each `→` rephrasing attached.

    `read_term_bank` puts every glossary node on its own line, so when the
    producer's `→` rephrasing OPENS with a bold span the arrow is left alone on
    its line (`…泣いてしまった` / `→` / `とても` / `嬉しい` / …) and the words that
    follow it are the paraphrase, not a continuation of the specimen. The earlier
    logic only started a rephrasing when text sat on the SAME line as the arrow,
    so a bare `→` was dropped and every following line glued onto the specimen —
    `嬉しさのあまり泣いてしまったとても嬉しいので泣いてしまった`, the exact run-on the
    UGD-08c beauty round filed five times (findings 1, 2, 4, 5, 13). Measured over
    edewakaru's four banks: 158 arrow-alone lines across 61 example fields; the
    3,779 arrows carrying their own text are unaffected.

    So the arrow toggles a rephrasing accumulator: once a `→` is seen, later
    continuation lines extend the CURRENT rephrasing rather than the specimen, and
    a following `→` opens the next rephrasing. A circled digit closes the example.
    """
    if not body:
        return ()
    examples: list[Example] = []
    sentence: str | None = None
    rephrasings: list[str] = []
    #: True once a `→` has opened a rephrasing for the current specimen. While set,
    #: an unmarked continuation line extends the last rephrasing, not the sentence.
    in_rephrasing = False

    def flush() -> None:
        nonlocal sentence, in_rephrasing
        if sentence:
            japanese = clean(sentence)
            if japanese:
                text = japanese
                for rephrasing in rephrasings:
                    cleaned = clean(rephrasing)
                    if cleaned:
                        text += f"\n→{cleaned}"
                marked = tuple(marker for marker in highlights if marker in japanese)
                # `english` stays None: the rephrasing is Japanese, and this
                # build never machine-translates.
                examples.append(Example(japanese=text, english=None, highlight=marked))
        sentence = None
        rephrasings.clear()
        in_rephrasing = False

    for line in body.split("\n"):
        if not line.strip():
            continue
        if _CIRCLED.match(line):
            flush()
            sentence = _CIRCLED.sub("", line).strip()
        elif _REPHRASING.match(line) and sentence:
            # A `→` opens a NEW rephrasing whether or not it carries its own text.
            # A bare arrow (the paraphrase begins with a bold span on the next
            # line) still starts one, so the words after it accumulate here rather
            # than fusing onto the specimen.
            rephrasings.append(_REPHRASING.sub("", line).strip())
            in_rephrasing = True
        elif in_rephrasing:
            rephrasings[-1] += line.strip()
        elif sentence:
            sentence += line.strip()
    flush()
    return tuple(examples)


__all__ = ["EdewakaruExtractor"]
