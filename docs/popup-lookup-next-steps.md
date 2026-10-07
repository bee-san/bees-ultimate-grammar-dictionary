# Popup lookup validation and next steps

This records how `v2026.10.07.2` was checked in real popup engines and what is
still open. See [lookup coverage](lookup-coverage.md) for what the dictionary
indexes and [the release notes](releases/v2026.10.07.2.md) for the change.

## What was wrong in v2026.10.07.1

Both released ZIPs were imported into the real engines and hovered at the
example highlights the sources provide. The problems were in the dictionary,
not in the popup apps:

- 616 rows had a reading that was not an exact kana spelling of their headword. Popups showed
  it as furigana (`かな【かなかなあ】`, `と【と～ない】`, `何のこと【なんのこ】`) and
  matched hovered text by it. Notation rows (`AながらB`) then surfaced for plain
  `ながら`, and typo rows (`と言いえ`) were the only path to their records.
- Producer synthetic lemmas (`ずにはいる`, `もする`, `ねばなる`) were headwords.
  Their conjugation class matched real negatives, so `ずにはいられなかった`
  produced `ずにはいる` with a passive trace, and the same article appeared twice.

## Engine checks

The 12,177 cases are up to three example highlights for each record in the six
sources that mark them: 文法, Bunpro, 絵でわかる日本語, 毎日のんびり日本語教師,
NINJAL and Yokubi. The cursor starts at the record's form inside the highlight,
or at the highlight itself, and up to 40 characters are scanned.

| Engine | Edition | Garbage-reading hits | Synthetic-headword hits | Source found |
| --- | --- | ---: | ---: | --- |
| Yomitan `77e20042` importer + `Translator` (fake IndexedDB) | v2026.10.07.1 original | 7,576 | 160 | baseline |
| same | v2026.10.07.2 original | 0 | 0 | unchanged (one 文法 example lost an inexact-reading match) |
| same | v2026.10.07.2 English | 0 | 0 | same as original |
| Hachidori hoshidicts WASM (`hdw_import`/`hdw_lookup`) | v2026.10.07.1 original | 7,588 | 173 | baseline |
| same | v2026.10.07.2 original and English | 0 | 0 | unchanged |

`make verify-popup` keeps the discriminating cases as regressions with the
pinned Yomitan transformer.

## Still open

- [ ] Hover the examples in [lookup coverage](lookup-coverage.md) in the Yomitan
  and Hachidori browser extensions. The engine checks above do not exercise the
  extensions' text scanners, scan-length settings or rendering.
- [ ] 669 kanji headwords have no source reading that spells them exactly. They
  show no furigana, and kana-written text does not find them. Adding readings
  needs source evidence; KANJIDIC can test a reading but cannot choose one.
- [ ] Some example highlights use a spelling that the record's headword lacks
  (`恐れがある` for `おそれがある`, `甲斐` for `かい`). Such spellings could become
  reviewed aliases.
- [ ] Polite headwords (`いたします`, `いらっしゃいます`) are not lemmas, so their
  conjugated forms (`いたしましょう`) do not reach them.
- [ ] Rows that only redirect (`ようなら` → see `ようだったら`) sit beside a
  separate content row with the same headword. Yomitan groups the two, but
  merging them would simplify the popup.
