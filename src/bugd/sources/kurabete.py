"""Kurabete — くらべてわかる日本語表現文型辞典 (J Research, 2008).

Source: a reviewed Yomitan conversion of the woodcube MDX edition (revision
`2026.10.20.2`), shipped as one archive and locked as `kurabete.zip`. The
producer checked all 363 patterns against page images of the printed book and
corrected OCR errors, omissions, the index and two diagrams.

The archive repeats every pattern under each of its lookup spellings: 1,070 term
rows share 363 bodies, keyed by the producer's sequence number. One grammar point
is emitted per sequence. The spelling that matches the printed headword becomes
`expression` and the other spellings become `variants`, so no lookup form is lost
and no body is counted more than once. The front-matter row (`資料`: preface,
terminology and notation key) is not a grammar point and is skipped.

Each body is a sequence of blocks tagged with the book's own labels:

    意味n   sense             -> `meaning`, one labelled line per sense
    例文n   examples          -> `examples`
    注意n   usage cautions    -> `notes`, with ○/× judged sentences
    対比n   contrasts         -> `explanation`, the book's core: each similar
                                 pattern with its explanation and ○/× pairs
    接続…   connection rules  -> `structure` (the producer's normalized
                                 notation; the book's original notation is
                                 kept in provenance)

Inline conventions are flattened to text the card renderer already understands:
the ○/×/∅ icon images become those characters, a struck-through kana becomes
`<s>…</s>` (as `ninjal_bunkei` writes it), subscripts become `₁₂`, and a stacked
alternative such as `給料｛○からいうと／×からすると｝社長と同額だ` keeps its
brackets. Diagram images cannot be carried into the dictionary, so their paths
are recorded in provenance; the prose around each diagram is kept.

Any block class this module does not recognise fails extraction rather than
being silently dropped.
"""

from __future__ import annotations

import io
import re
import zipfile

from ..jsonio import MalformedPayload, load_json
from ..model import Example, GrammarPoint
from .base import Extractor, ExtractResult, assign_row_uids, load_source_lock, write_points_jsonl
from .community import clean
from .registry import register_extractor

ARCHIVE_NAME = "kurabete.zip"
SOURCE_LABEL = "くらべてわかる日本語表現文型辞典"
#: Producer revision the parser was written against. A different archive must be
#: reviewed (and this pin moved) before it can be extracted.
EXPECTED_REVISION = "2026.10.20.2"
FRONT_MATTER_TAG = "資料"
GRAMMAR_TAG = "文型"
TERM_ROW_LENGTH = 8

#: Inline icon images and the characters the book prints for them.
_ICON_TEXT = {
    "image/circle-regular.svg": "○",
    "image/xmark-solid.svg": "×",
    "image/empty-set.svg": "∅",
    "image/bracket_left.svg": "｛",
    "image/bracket_left4.svg": "｛",
    "image/bracket_right.svg": "｝",
    "image/bracket_right4.svg": "｝",
}
_SUBSCRIPTS = str.maketrans("0123456789０１２３４５６７８９", "₀₁₂₃₄₅₆₇₈₉₀₁₂₃₄₅₆₇₈₉")

#: Block sections of an entry body, by producer class.
_SECTION_CLASSES = ("meaning", "examples", "notes", "comparisons", "usages")
#: Headword placeholders: pattern slots (Ａ, Ｂ, Ｘ…) and subscripts.
_HEADWORD_SLOTS = re.compile(r"[Ａ-Ｚ₀-₉\s（）()〜～…]")


def _classes(node: object) -> tuple[str, ...]:
    if isinstance(node, dict):
        data = node.get("data")
        if isinstance(data, dict) and isinstance(data.get("class"), str):
            return tuple(data["class"].split())
    return ()


def _children(node: object) -> list:
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        content = node.get("content")
        if isinstance(content, list):
            return content
        if content is not None:
            return [content]
    return []


class _Inline:
    """Flatten inline structured content to text, collecting diagram paths."""

    def __init__(self) -> None:
        self.images: list[str] = []

    def text(self, node: object) -> str:
        if isinstance(node, str):
            return node
        if isinstance(node, list):
            return "".join(self.text(child) for child in node)
        if not isinstance(node, dict):
            return ""
        tag = node.get("tag")
        classes = _classes(node)
        if tag in ("rt", "rp", "summary"):
            return ""
        if tag == "br":
            return "\n"
        if tag == "img":
            path = node.get("path")
            if path in _ICON_TEXT:
                return _ICON_TEXT[path]
            if isinstance(path, str) and path not in self.images:
                self.images.append(path)
            return ""
        if "place_holder" in classes:
            return " "
        inner = "".join(self.text(child) for child in _children(node))
        if "sub" in classes:
            return inner.translate(_SUBSCRIPTS)
        if "linethrough" in classes:
            return f"<s>{inner}</s>" if inner else ""
        if "multiline" in classes:
            lines = [self.text(child).strip() for child in _children(node)]
            return "／".join(line for line in lines if line)
        return inner


def _label(block: dict, inline: _Inline) -> str:
    """The book's own tag label for a block (意味1, 例文1, 接続1～4 …)."""
    for child in _children(block):
        if "tag" in _classes(child):
            return clean(inline.text(child)) or ""
    return ""


def _body(block: dict, inner_class: str) -> list:
    for child in _children(block):
        if inner_class in _classes(child):
            return _children(child)
    raise MalformedPayload(f"kurabete: a {_classes(block)} block has no {inner_class}")


def _lines(nodes: list, inline: _Inline) -> list[str]:
    """One text line per block-level child (explanation, ○ / × sentence …)."""
    lines: list[str] = []
    for node in nodes:
        if _is_block_wrapper(node):
            # A note, or an explanation holding a/b illustration rows: each
            # block child is its own line.
            lines.extend(_lines(_children(node), inline))
            continue
        text = clean(inline.text(node))
        if text:
            lines.append(text)
    return lines


#: Leaf lines whose block children are layout, not separate lines.
_LEAF_LINES = frozenset({"correct", "wrong", "multiline", "line"})


def _is_block_wrapper(node: object) -> bool:
    """A div made only of block-level divs, e.g. a note or an a/b illustration pair."""
    if not isinstance(node, dict) or node.get("tag") != "div":
        return False
    if _LEAF_LINES & set(_classes(node)):
        return False
    children = [child for child in _children(node) if "clear" not in _classes(child)]
    return bool(children) and all(
        isinstance(child, dict) and child.get("tag") in ("div", "details") for child in children
    )


def _entry_container(content: object) -> dict:
    """Return the div whose children are the number, grammar and sections."""
    stack = [content]
    while stack:
        node = stack.pop(0)
        if isinstance(node, dict):
            if any("number" in _classes(child) for child in _children(node)):
                return node
            stack.extend(_children(node))
        elif isinstance(node, list):
            stack.extend(node)
    raise MalformedPayload("kurabete: entry body has no numbered container")


def parse_body(glossary: list) -> dict:
    """Parse one entry body into labelled fields."""
    if len(glossary) != 1 or not isinstance(glossary[0], dict):
        raise MalformedPayload("kurabete: expected one structured-content glossary item")
    inline = _Inline()
    container = _entry_container(glossary[0].get("content"))

    number = ""
    headword = ""
    derivations: list[str] = []
    meanings: list[tuple[str, str]] = []
    examples: list[Example] = []
    notes: list[str] = []
    comparisons: list[str] = []
    usages: list[tuple[str, list[str]]] = []
    original_notation: list[str] = []

    for block in _children(container):
        classes = _classes(block)
        if "number" in classes:
            number = clean(inline.text(block)) or ""
            continue
        if "grammar" in classes:
            for node in _walk(block):
                node_classes = _classes(node)
                if "headword" in node_classes:
                    headword = clean(inline.text(node)) or ""
                elif "derivation" in node_classes:
                    text = clean(inline.text(node))
                    if text:
                        derivations.append(text)
            continue
        section = next((name for name in _SECTION_CLASSES if name in classes), None)
        if section is None:
            raise MalformedPayload(f"kurabete: unrecognised entry block {classes!r}")
        label = _label(block, inline)
        if section == "meaning":
            text = "".join(
                inline.text(child) for child in _children(block) if "text" in _classes(child)
            )
            meanings.append((label, clean(text) or ""))
        elif section == "examples":
            for example in _body(block, "examples__inner"):
                sentence = "".join(
                    inline.text(child)
                    for child in _children(example)
                    if "list_number" not in _classes(child)
                )
                sentence = clean(sentence)
                if sentence:
                    examples.append(Example(japanese=sentence))
        elif section == "notes":
            lines = _lines(_body(block, "notes__inner"), inline)
            if lines:
                notes.append("\n".join([f"【{label}】", *lines]))
        elif section == "comparisons":
            groups = [
                "\n".join(_lines(_children(comparison), inline))
                for comparison in _body(block, "comparisons_inner")
            ]
            groups = [group for group in groups if group]
            if groups:
                comparisons.append("\n\n".join([f"【{label}】", *groups]))
        elif section == "usages":
            current: list[str] = []
            for child in _body(block, "usages_inner"):
                if "original-notation" in _classes(child):
                    original_notation.extend(_lines(_children(child), inline))
                    continue
                text = clean(inline.text(child))
                if text:
                    current.append(text)
            usages.append((label, current))

    if not number or not headword:
        raise MalformedPayload("kurabete: entry is missing its number or headword")
    if not meanings:
        raise MalformedPayload(f"kurabete: entry {number} has no 意味 block")

    if len(meanings) == 1:
        meaning = meanings[0][1]
    else:
        meaning = "\n".join(f"{label}：{text}" for label, text in meanings)
    if len(usages) == 1:
        structure_lines = usages[0][1]
    else:
        structure_lines = [
            line for label, lines in usages for line in ([f"{label}："] + lines)
        ]
    pattern = headword.replace(" ", "")
    if derivations:
        pattern += "（" + "／".join(derivations) + "）"
    return {
        "number": number,
        "headword": headword,
        "derivations": derivations,
        "meaning": clean(meaning),
        "structure": clean("\n".join([pattern, *structure_lines])),
        "notes": clean("\n\n".join(notes)),
        "explanation": clean("\n\n".join(comparisons)),
        "examples": tuple(examples),
        "originalNotation": original_notation,
        "images": inline.images,
        "senses": len(meanings),
    }


def _walk(node: object):
    yield node
    for child in _children(node):
        yield from _walk(child)


def _canonical(headword: str, forms: list[str]) -> str:
    """Pick the lookup spelling that matches the printed headword."""
    bare = _HEADWORD_SLOTS.sub("", headword)
    for form in forms:
        if form == bare:
            return form
    # Otherwise the longest spelling the headword contains, then bank order.
    contained = [form for form in forms if form in bare]
    if contained:
        return max(contained, key=len)
    return forms[0]


def read_rows(archive: bytes) -> tuple[dict, list[tuple[str, list]]]:
    """Read the archive index and every term row, in member order."""
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        index = load_json(bundle.read("index.json").decode("utf-8-sig"))
        members = sorted(
            (name for name in bundle.namelist() if re.fullmatch(r"term_bank_\d+\.json", name)),
            key=lambda name: int(re.findall(r"\d+", name)[0]),
        )
        if not members:
            raise MalformedPayload("kurabete: archive has no term banks")
        rows: list[tuple[str, list]] = []
        for member in members:
            payload = load_json(bundle.read(member).decode("utf-8"))
            if not isinstance(payload, list):
                raise MalformedPayload(f"kurabete: {member} is not a JSON array")
            for position, row in enumerate(payload):
                if not isinstance(row, list) or len(row) != TERM_ROW_LENGTH:
                    raise MalformedPayload(f"kurabete: {member}[{position}] is not a term row")
                rows.append((member, row))
    return index, rows


def parse_rows(rows: list[tuple[str, list]]) -> tuple[list[GrammarPoint], dict]:
    groups: dict[int, dict] = {}
    skipped_front_matter = 0
    for member, row in rows:
        expression, reading, tag, _rules, _score, glossary, sequence, _term_tags = row
        if not isinstance(expression, str) or not expression.strip():
            raise MalformedPayload(f"kurabete: {member} has an empty expression")
        if tag == FRONT_MATTER_TAG:
            skipped_front_matter += 1
            continue
        if tag != GRAMMAR_TAG or not isinstance(sequence, int) or isinstance(sequence, bool):
            raise MalformedPayload(f"kurabete: unexpected row {expression!r} ({tag!r}, {sequence!r})")
        group = groups.setdefault(
            sequence, {"glossary": glossary, "forms": [], "readings": {}, "members": []}
        )
        if glossary != group["glossary"]:
            raise MalformedPayload(f"kurabete: sequence {sequence} has differing bodies")
        if expression not in group["forms"]:
            group["forms"].append(expression)
        if isinstance(reading, str) and reading.strip() and reading != expression:
            group["readings"][expression] = reading
        if member not in group["members"]:
            group["members"].append(member)

    points: list[GrammarPoint] = []
    for sequence in sorted(groups):
        group = groups[sequence]
        body = parse_body(group["glossary"])
        if body["number"] != str(sequence):
            raise MalformedPayload(
                f"kurabete: sequence {sequence} prints number {body['number']!r}"
            )
        forms = group["forms"]
        expression = _canonical(body["headword"], forms)
        provenance: dict[str, object] = {
            "sourceLabel": SOURCE_LABEL,
            "bankMembers": group["members"],
            "entryNumber": sequence,
            "headword": body["headword"],
            "lookupForms": [
                {"expression": form, **({"reading": group["readings"][form]} if form in group["readings"] else {})}
                for form in forms
            ],
        }
        if body["derivations"]:
            provenance["derivations"] = body["derivations"]
        if body["originalNotation"]:
            provenance["originalNotation"] = body["originalNotation"]
        if body["images"]:
            provenance["omittedImages"] = body["images"]
        points.append(
            GrammarPoint(
                source=KurabeteExtractor.name,
                source_id=str(sequence),
                expression=expression,
                variants=tuple(form for form in forms if form != expression),
                reading=group["readings"].get(expression),
                meaning=body["meaning"],
                structure=body["structure"],
                explanation=body["explanation"],
                notes=body["notes"],
                examples=body["examples"],
                provenance=provenance,
            )
        )
    stats = {
        "termRows": len(rows),
        "frontMatterRows": skipped_front_matter,
        "points": len(points),
        "lookupForms": sum(1 + len(point.variants) for point in points),
        "examples": sum(len(point.examples) for point in points),
        "withNotes": sum(1 for point in points if point.notes),
        "withContrasts": sum(1 for point in points if point.explanation),
        "omittedImages": sum(len(point.provenance.get("omittedImages", ())) for point in points),
    }
    return points, stats


@register_extractor
class KurabeteExtractor(Extractor):
    name = "kurabete"
    label = SOURCE_LABEL

    def extract(self) -> ExtractResult:
        lock = load_source_lock(self.input_dir)
        if ARCHIVE_NAME not in lock:
            raise MalformedPayload(f"kurabete: locked input is missing: {ARCHIVE_NAME}")
        index, rows = read_rows(self.read_locked_bytes(ARCHIVE_NAME))
        if index.get("title") != SOURCE_LABEL or index.get("revision") != EXPECTED_REVISION:
            raise MalformedPayload(
                f"kurabete: archive is {index.get('title')!r} {index.get('revision')!r}, "
                f"expected {SOURCE_LABEL!r} {EXPECTED_REVISION!r}"
            )
        points, stats = parse_rows(rows)
        points = assign_row_uids(self.name, points)
        write_points_jsonl(self.input_dir, points)
        stats["revision"] = index["revision"]
        return ExtractResult(
            source=self.name,
            points=points,
            consumed={ARCHIVE_NAME: lock[ARCHIVE_NAME]["sha256"]},
            stats=stats,
        )


__all__ = ["KurabeteExtractor", "parse_body", "parse_rows", "read_rows"]
