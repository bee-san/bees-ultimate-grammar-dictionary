#!/usr/bin/env python3
"""Propose kana readings for kanji headwords that no source spells exactly.

This is an acquisition tool, like `translate_english.py`: normal builds only read
its committed output, `website/data/headword-readings.json`.

Three independent analyses are compared for each headword:

* **JMdict** (EDRDG, CC BY-SA 4.0): the whole headword as a written form, or
  else each Sudachi token's dictionary form, with its reading aligned onto the
  conjugated surface;
* **Sudachi** (SudachiDict-full): the morphological reading of the whole
  headword in context;
* **Jiten** (jiten.moe's open-source JMdict-based parser): each parsed word's
  furigana aligned onto the surface;
* **gloss**: a reading the source itself prints beside the headword, as in
  IMABI's `～棟（むね・トウ）` or its flattened furigana `～滴てき`;
* **context**: Sudachi's reading of the headword wherever it occurs as a whole
  token in its own records' examples and explanations. Single kanji are mostly
  counters and suffixes (`杯` is はい after a number, not さかずき), which only
  the source's own sentences can tell apart.

Every candidate must pass `is_exact_reading`. A reading is accepted only when
JMdict lists the whole headword, or when at least two analyses agree and none
proposes a different valid reading. Everything else is written to the review
section with its evidence, and only a reviewed decision in `REVIEWED` resolves it.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_site import snapshot_inputs  # noqa: E402
from bugd.headword_readings import CATALOG, needs_reading  # noqa: E402
from bugd.readings import is_exact_reading, normalize_kana  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
JMDICT_URL = "http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz"
JITEN = "https://api.jiten.moe/api/vocabulary"
NUMERAL = re.compile(r"[0-9０-９〇一二三四五六七八九十百千万何幾数半]+")
KANJI_RUN = re.compile(r"[\u3400-\u9fff\uf900-\ufaff々〆ヶヵ]+")

#: Reviewed decisions for headwords the analyses could not settle. Each value is
#: the reading (or None to leave the headword without one) and the reason.
REVIEWED: dict[str, tuple[str | None, str]] = {
    # IMABI counter and affix lessons: the counter reading, as the lesson
    # prints it or uses it after numbers.
    "基": ("き", "counter ～基, printed き by IMABI Counters VIII"),
    "夜": ("や", "counter ～夜 (一夜・三夜), printed や・よ by IMABI"),
    "女": ("じょ", "counter ～女 in IMABI Counters VIII, printed じょ"),
    "男": ("なん", "counter ～男 in IMABI Counters VIII, printed なん"),
    "対": ("つい", "counter ～対, printed つい by IMABI Counters VIII"),
    "尾": ("び", "counter for fish ～尾 in IMABI Counters II"),
    "巻": ("かん", "counter for volumes ～巻 in IMABI Counters II"),
    "度": ("ど", "frequency counter ～度; its sentences use ど 65 times"),
    "日": ("にち", "day counter ～日（間）in IMABI Time Counters I"),
    "歩": ("ほ", "counter for steps ～歩 in IMABI Counters I"),
    "体": ("からだ", "IMABI's “The Body” lessons"),
    "味": ("み", "nominalizing suffix ～味 (甘味) in IMABI Adjective Nominalization"),
    "的": ("てき", "suffix ～的 (Bunpro “~ly・~like・~al”)"),
    "等": ("ら", "plural suffix ～ら・等 in IMABI Pluralization"),
    "真": ("ま", "prefix 真～, printed 接頭辞の「真（ま）」 by IMABI and ま by Bunpro"),
    "無": ("む", "negative prefix 無～; its sentences use む"),
    "故": ("ゆえ", "IMABI lesson ～故, 所以, 謂れ, & 由"),
    "暦": ("こよみ", "the word 暦 in IMABI Calendar Systems of Japan; JMdict こよみ"),
    # Whole words JMdict lists that the per-kanji gate now composes.
    "各々": ("おのおの", "JMdict 各々"),
    "就中": ("なかんずく", "JMdict 就中"),
    "所以": ("ゆえん", "JMdict 所以; IMABI lesson ～故, 所以, 謂れ, & 由"),
    "謂れ": ("いわれ", "JMdict 謂れ; IMABI lesson ～故, 所以, 謂れ, & 由"),
    "当って": ("あたって", "JMdict 当る（あたる）, shortened okurigana"),
    # Analyses that disagreed or were wrong.
    "で言うと": ("でいうと", "standard reading of 言う; Sudachi's ゆう is colloquial"),
    "来ます": ("きます", "polite form of 来る"),
    "時間直示": ("じかんちょくじ", "直示 (deixis) is ちょくじ; Sudachi read なおじ"),
    "何某か": ("なにがしか", "JMdict 何某 なにがし; Sudachi read なにぼう"),
    "給ふ": ("たまふ", "classical 給ふ; its sentences use たまふ 26 times"),
    "尽くめ": ("ずくめ", "JMdict lists ずくめ and づくめ; ずくめ is the modern spelling"),
    "さるこ事がら": (None, "typo row for もさることながら; it has no reading of its own"),
    # A popup also matches hovered text by the reading. These readings spell a
    # different kana headword, mostly a particle or auxiliary, so the counter or
    # affix would come up for every か, わ, よ, ます or だい in a sentence.
    **{term: (None, f"its reading {kana} would also match the unrelated kana headword {kana}")
       for term, kana in {
        "化": "か", "課": "か", "羽": "わ", "余": "よ", "夜": "や", "度": "ど", "基": "き", "気": "き",
        "増す": "ます", "年": "ねん", "杯": "はい", "枚": "まい", "歳": "さい", "男": "なん", "遍": "へん",
        "錠": "じょう", "未": "み", "真": "ま", "対": "つい", "回": "かい", "階": "かい", "代": "だい",
        "台": "だい", "第": "だい", "各": "かく", "画": "かく", "着る": "きる", "返る": "かえる",
        "幾": "いく"}.items()},
    # One-mora readings of counters and prefixes would match the first kana of
    # almost any word (個/戸 こ in これ, この, ここ). 味 み and 等 ら are kept:
    # their kana headwords are the same suffixes.
    **{term: (None, f"its one-mora reading {kana} would match the start of unrelated words")
       for term, kana in {"不": "ふ", "個": "こ", "戸": "こ", "尾": "び", "歩": "ほ", "無": "む",
                          "部": "ぶ", "非": "ひ"}.items()},
    # Verbs whose inflected reading spells a common word: それ (逸れ-), わたし
    # (渡し), たって (立って, also a grammar headword).
    **{term: (None, f"its inflections would match the unrelated word {word}")
       for term, word in {"逸れる": "それ", "渡す": "わたし", "立つ": "たって"}.items()},
    # Only Sudachi read these grammar-term compounds; each part checked in JMdict.
    **{term: (reading, "compound of JMdict words, read by Sudachi; checked by hand") for term, reading in {
        "ローマ字表記": "ろーまじひょうき", "他受動詞": "たじゅどうし", "使役受身": "しえきうけみ",
        "促音化": "そくおんか", "古典文法": "こてんぶんぽう", "幽霊字": "ゆうれいじ",
        "形容詞語幹": "けいようしごかん", "撥音化": "はつおんか", "撥音添加": "はつおんてんか",
        "敵性語禁止": "てきせいごきんし", "文法用語": "ぶんぽうようご", "日本語学習": "にほんごがくしゅう",
        "時間表現": "じかんひょうげん", "漢語動詞": "かんごどうし", "自他動詞": "じたどうし",
        "自受動詞": "じじゅどうし", "連体修飾": "れんたいしゅうしょく", "連用中止": "れんようちゅうし",
        "連用中止形": "れんようちゅうしけい", "非過去形": "ひかこけい"}.items()},
}


def jmdict_readings(path: pathlib.Path) -> tuple[dict[str, dict[str, list[int]]], str]:
    raw = path.read_bytes()
    table: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    created = ""
    text = gzip.decompress(raw)
    match = re.search(rb"JMdict created: ([0-9-]+)", text)
    if match:
        created = match[1].decode()
    for _, element in ET.iterparse(gzip.open(path), events=("end",)):
        if element.tag != "entry":
            continue
        seq = int(element.findtext("ent_seq"))
        written = [k.findtext("keb") for k in element.findall("k_ele")]
        for r_ele in element.findall("r_ele"):
            if r_ele.find("re_nokanji") is not None:
                continue
            restricted = [x.text for x in r_ele.findall("re_restr")] or written
            for keb in restricted:
                table[keb][normalize_kana(r_ele.findtext("reb"))].append(seq)
        element.clear()
    return table, f"sha256:{hashlib.sha256(raw).hexdigest()} created {created}"


def align(written: str, reading: str) -> dict[str, str] | None:
    """Map each kanji run of a written form to its part of the reading."""
    written, reading = normalize_kana(written), normalize_kana(reading)
    runs = KANJI_RUN.findall(normalize_kana(written))
    pattern = "".join("(.+?)" if KANJI_RUN.fullmatch(part) else re.escape(part)
                      for part in re.split(f"({KANJI_RUN.pattern})", written) if part)
    match = re.fullmatch(pattern, reading)
    if not match:
        return None
    return dict(zip(runs, match.groups()))


def apply_runs(surface: str, mapping: dict[str, str]) -> str | None:
    out = []
    for part in re.split(f"({KANJI_RUN.pattern})", normalize_kana(surface)):
        if not part:
            continue
        if KANJI_RUN.fullmatch(part):
            if part not in mapping:
                return None
            out.append(mapping[part])
        else:
            out.append(part)
    return "".join(out)


def furigana_runs(text: str) -> dict[str, str]:
    """`いつの間[ま]にか` -> {'間': 'ま'}."""
    return {normalize_kana(k): normalize_kana(r)
            for k, r in re.findall(f"({KANJI_RUN.pattern})\\[([^\\]]+)\\]", text)}


class Jiten:
    def __init__(self, cache_path: pathlib.Path, offline: bool):
        self.path = cache_path
        self.offline = offline
        self.cache = json.loads(cache_path.read_text()) if cache_path.exists() else {"parse": {}, "word": {}}

    def _get(self, url: str):
        for attempt in range(6):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "bees-ultimate-grammar-dictionary"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    time.sleep(0.25)  # stay well inside the public 300/minute limit
                    return json.loads(response.read())
            except urllib.error.HTTPError as error:
                if error.code != 429:
                    raise
                time.sleep(15 * (attempt + 1))
        raise RuntimeError(f"Jiten kept rate-limiting {url}")

    def parse(self, text: str) -> list[dict]:
        if text not in self.cache["parse"]:
            if self.offline:
                raise KeyError(f"Jiten parse not cached: {text}")
            self.cache["parse"][text] = self._get(f"{JITEN}/parse?text={urllib.parse.quote(text)}")
        return self.cache["parse"][text]

    def furigana(self, word_id: int, reading_index: int) -> str | None:
        key = f"{word_id}/{reading_index}"
        if key not in self.cache["word"]:
            if self.offline:
                raise KeyError(f"Jiten word not cached: {key}")
            data = self._get(f"{JITEN}/{word_id}/{reading_index}")
            readings = [data.get("mainReading") or {}, *(data.get("alternativeReadings") or [])]
            chosen = next((r for r in readings if r.get("readingIndex") == reading_index), readings[0])
            self.cache["word"][key] = chosen.get("text")
        return self.cache["word"][key]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


def record_texts(entry: dict) -> list[str]:
    texts = []
    for point in entry["contributions"]:
        texts += [example.get("japanese") or "" for example in point.get("examples") or []]
        texts += [point.get(field) or "" for field in ("explanation", "explanation_ja", "meaning",
                                                       "structure", "notes", "nuance_ja")]
    return [t for t in texts if t]


def context_readings(expression: str, texts: list[str], tokenizer) -> dict[str, int]:
    from sudachipy import SplitMode

    counts: dict[str, int] = defaultdict(int)
    for text in texts:
        if expression not in text:
            continue
        for chunk in re.split(r"(?<=[。！？\n])", text):
            if expression not in chunk or len(chunk.encode()) > 40000:
                continue
            # Whole words only: splitting compounds (旧暦 -> 暦) would count
            # their on'yomi. A number + counter word (五本) is split, though.
            for token in tokenizer.tokenize(chunk, SplitMode.C):
                surface = token.surface()
                if surface == expression:
                    readings = [token.reading_form()]
                elif surface.endswith(expression) and NUMERAL.fullmatch(surface[:-len(expression)]):
                    readings = [t.reading_form() for t in tokenizer.tokenize(surface, SplitMode.A)
                                if t.surface() == expression]
                else:
                    continue
                for reading in map(normalize_kana, readings):
                    if is_exact_reading(expression, reading):
                        counts[reading] += 1
    return dict(sorted(counts.items(), key=lambda item: -item[1]))


def source_glosses(expression: str, texts: list[str]) -> list[str]:
    """Readings a record prints next to its headword, in the order given."""
    kana = "[ぁ-ゖァ-ヺー]+"
    patterns = [rf"{re.escape(expression)}[（(]\s*({kana}(?:\s*[・、/／]\s*{kana})*)\s*[）)]",
                rf"[～〜]{re.escape(expression)}({kana})(?=[\s\xa0（(,、。]|$)"]
    found: list[str] = []
    for text in texts:
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                for part in re.split(r"\s*[・、/／]\s*", match[1]):
                    reading = normalize_kana(part)
                    if is_exact_reading(expression, reading) and reading not in found:
                        found.append(reading)
    return found


def resolve(expression: str, jmdict, tokenizer, jiten: Jiten, texts: list[str]) -> dict:
    from sudachipy import SplitMode

    evidence: dict[str, object] = {"context": context_readings(expression, texts, tokenizer),
                                   "gloss": source_glosses(expression, texts)}
    valid = lambda reading: reading if reading and is_exact_reading(expression, reading) else None  # noqa: E731

    whole = jmdict.get(expression)
    if whole:
        evidence["jmdictWhole"] = {reading: sorted(seqs) for reading, seqs in sorted(whole.items())
                                  if valid(reading)}

    tokens = tokenizer.tokenize(expression, SplitMode.C)
    evidence["sudachi"] = valid(normalize_kana("".join(m.reading_form() for m in tokens)))

    # JMdict, token by token: the dictionary form's reading mapped onto the surface.
    mapping: dict[str, str] = {}
    seqs: list[int] = []
    for token in tokens:
        surface = token.surface()
        if not KANJI_RUN.search(surface):
            continue
        options = jmdict.get(token.dictionary_form()) or jmdict.get(surface) or {}
        aligned = [(align(token.dictionary_form() if token.dictionary_form() in jmdict else surface, r), s)
                   for r, s in options.items()]
        aligned = [(m, s) for m, s in aligned if m]
        token_reading = normalize_kana(token.reading_form())
        # Prefer the JMdict reading Sudachi's own token reading agrees with.
        best = next(((m, s) for m, s in aligned if apply_runs(surface, m) == token_reading), None)
        if best is None and len({json.dumps(m, sort_keys=True) for m, _ in aligned}) == 1:
            best = aligned[0]
        if best is None:
            mapping = {}
            break
        mapping.update(best[0])
        seqs += best[1]
    composed = valid(apply_runs(expression, mapping)) if mapping else None
    if composed:
        evidence["jmdictTokens"] = {"reading": composed, "entries": sorted(set(seqs))}

    # Jiten: parse the headword, then each word's furigana.
    runs: dict[str, str] = {}
    for word in jiten.parse(expression):
        if word.get("wordId") and KANJI_RUN.search(word.get("originalText") or ""):
            text = jiten.furigana(word["wordId"], word.get("readingIndex") or 0)
            runs.update(furigana_runs(text or ""))
    evidence["jiten"] = valid(apply_runs(expression, runs)) if runs else None

    return evidence


def fold(context: dict[str, int], candidates) -> dict[str, int]:
    """Count a context reading towards the candidate it is a sound change of
    (`一杯` gives ばい for はい, `一本` ぽん for ほん)."""
    from bugd.readings import _variants

    folded: dict[str, int] = defaultdict(int)
    for reading, count in context.items():
        base = reading if reading in candidates else next(
            (c for c in candidates if reading in _variants(c)), None)
        if base:
            folded[base] += count
    return dict(sorted(folded.items(), key=lambda item: -item[1]))


def decide(expression: str, evidence: dict) -> dict:
    whole = evidence.get("jmdictWhole") or {}
    votes = defaultdict(list)
    for name, value in (("sudachi", evidence.get("sudachi")), ("jiten", evidence.get("jiten")),
                        ("jmdictTokens", (evidence.get("jmdictTokens") or {}).get("reading"))):
        if value:
            votes[value].append(name)
    context = evidence.get("context") or {}
    if expression in REVIEWED:
        reading, note = REVIEWED[expression]
        return {"reading": reading, "basis": f"reviewed: {note}"}

    gloss = evidence.get("gloss") or []
    if gloss:
        counts = fold(context, set(gloss) | set(whole))
        top = next(iter(counts), None)
        if top and top not in gloss and counts[top] >= 3 and counts[top] > 2 * max(counts.get(g, 0) for g in gloss):
            return {"reading": None, "basis": "review: the source prints a reading its sentences rarely use"}
        if len(gloss) == 1:
            return {"reading": gloss[0], "basis": "printed by the source beside the headword"}
        counts = fold(context, gloss)
        choice = next(iter(counts), gloss[0])
        return {"reading": choice, "basis": f"source prints {'・'.join(gloss)}; "
                                            + ("most used in its sentences" if counts else "first listed")}
    if len(whole) == 1:
        return {"reading": next(iter(whole)), "basis": "JMdict lists the whole headword with one reading"}
    if len(whole) > 1:
        counts = fold(context, whole)
        total = sum(counts.values())
        top = next(iter(counts), None)
        if top and counts[top] >= 2 and counts[top] / total >= 0.6:
            return {"reading": top, "basis": f"JMdict whole headword; {counts[top]} of {total} uses in its sentences"}
        agreed = [r for r in whole if votes.get(r)]
        if not counts and len(agreed) == 1:
            return {"reading": agreed[0], "basis": f"JMdict whole headword; chosen by {', '.join(votes[agreed[0]])}"}
        return {"reading": None, "basis": "review: JMdict lists several readings"}
    total = sum(context.values())
    top = next(iter(context), None)
    if top and context[top] / total >= 0.8 and (context[top] >= 2 or votes.get(top)) and \
            all(v == top for v in votes):
        return {"reading": top, "basis": f"{context[top]} of {total} uses in its sentences"}
    if len(votes) == 1:
        reading, names = next(iter(votes.items()))
        if len(names) >= 2:
            return {"reading": reading, "basis": f"agreement of {', '.join(names)}"}
        return {"reading": None, "basis": f"review: only {names[0]}"}
    if votes:
        return {"reading": None, "basis": "review: analyses disagree"}
    return {"reading": None, "basis": "review: no valid reading"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jmdict", type=pathlib.Path, required=True, help="JMdict_e.gz from EDRDG")
    parser.add_argument("--snapshot", type=pathlib.Path, default=ROOT / "website/data")
    parser.add_argument("--jiten-cache", type=pathlib.Path, default=ROOT / "data/readings/jiten-responses.json")
    parser.add_argument("--offline", action="store_true", help="use only cached Jiten responses")
    args = parser.parse_args()

    import sudachipy
    from importlib.metadata import version
    from sudachipy import Dictionary

    corpus, _, _ = snapshot_inputs(args.snapshot)
    texts: dict[str, list[str]] = defaultdict(list)
    for entry in corpus["entries"]:
        if needs_reading(entry):
            texts[entry["expression"]] += record_texts(entry)
    targets = sorted(texts)
    jmdict, jmdict_pin = jmdict_readings(args.jmdict)
    tokenizer = Dictionary(dict="full").create()
    args.jiten_cache.parent.mkdir(parents=True, exist_ok=True)
    jiten = Jiten(args.jiten_cache, args.offline)
    records = {}
    try:
        for expression in targets:
            evidence = resolve(expression, jmdict, tokenizer, jiten, texts[expression])
            record = decide(expression, evidence)
            if record["reading"] and not is_exact_reading(expression, record["reading"]):
                raise ValueError(f"{expression}: {record['reading']} does not spell the headword")
            records[expression] = {**record, "evidence": evidence}
    finally:
        if not args.offline:
            jiten.save()
    catalog = {
        "schemaVersion": 1,
        "provenance": {
            "jmdict": f"{JMDICT_URL} {jmdict_pin} (EDRDG, CC BY-SA 4.0)",
            "sudachi": f"sudachipy {sudachipy.__version__}, SudachiDict-full {version('sudachidict_full')} (Apache-2.0)",
            "jiten": f"{JITEN}/parse and /{{wordId}}/{{readingIndex}} (Apache-2.0), responses in "
                     f"{args.jiten_cache.relative_to(ROOT)}",
        },
        "records": records,
    }
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    resolved = sum(1 for r in records.values() if r["reading"])
    print(json.dumps({"targets": len(targets), "resolved": resolved,
                      "review": {e: r["basis"] for e, r in records.items() if not r["reading"]}},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
