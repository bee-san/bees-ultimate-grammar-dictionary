# Popup lookup handoff and next steps

Implementation and release work is paused at the user's request. This document
records the current state and proposed follow-up work for when it resumes.

## Published baseline

- [Release v2026.10.07.1](https://github.com/bee-san/bees-ultimate-grammar-dictionary/releases/tag/v2026.10.07.1)
  is already published from commit
  `b0cb057c76cf143b213cb672a92214b197f4e7fd`.
- Both editions contain 7,633 term-bank rows covering 9,152 source records across
  13 sources. All records have a Japanese lookup form or topic label.
- IMABI contributes 495 lessons indexed under 1,400 Japanese terms, including
  `について`, `ことにする` and conjugated lookup support.
- The raw IMABI pages, frozen source corpus, English translation cache, lookup
  catalogs, overrides and compatibility headwords are committed. Normal release
  builds use the committed snapshot without scraping or translation calls.

See [lookup coverage](lookup-coverage.md),
[release notes](releases/v2026.10.07.1.md) and
[build documentation](website.md) for the implementation and reproduction details.

The existing checks cover packaged records, source disclosures, article links,
schemas, checksums and 16 sentence/cursor cases per ZIP using the pinned upstream
Yomitan engine. They do **not** constitute an import or hover test in the actual
browser extension. Japanese topic coverage also does not mean that every lesson
can be found by hovering every example sentence.

## 1. Verify the published release in real popup apps

- [ ] Import or update to v2026.10.07.1 in Yomitan and in the popup app used by the
  person reporting the problem. Record app/browser versions, dictionary revision,
  scan length, cursor position and enabled dictionaries.
- [ ] Run the sentence/hover examples in [lookup coverage](lookup-coverage.md)
  against each edition. Check basic particles, compound constructions, conjugated
  endings, kana/kanji spellings and the non-IMABI examples.
- [ ] Open the source disclosures and follow "Read all explanations." Verify the
  expected source lesson appears, extra senses are accessible, and each edition
  opens the correct language route. Confirm older installed dictionary links
  still reach their articles.
- [ ] Check topic queries such as `母音` and `古典文法` separately from sentence
  hovering, and confirm source-page-only listings are clearly labelled.

Acceptance: attach an app/version test matrix with observed results for both
editions. Record failures as reproducible cases rather than assuming the engine
tests prove the browser workflow.

## 2. Turn reported misses into focused regressions

- [ ] For each miss, capture the exact Japanese sentence, cursor start, expected
  source and lesson URL, installed revision, and actual popup result.
- [ ] Determine whether the cause is an old installation or scan setting, a
  missing literal alias, a reading or inflection rule, or a hidden disclosure.
  Check the actual released ZIP before changing extraction.
- [ ] Add a regression at the failing layer: packaged sentence matching in
  `scripts/verify_popup.mjs`, alias/catalog tests in
  `tests/test_popup_lookup.py` or `tests/test_imabi_lookup.py`, or rendering tests
  in `tests/test_banks_card.py` and `tests/test_english_website.py`.
- [ ] Implement only source-supported aliases or rendering corrections, with a
  negative case where the change could introduce unrelated matches.

Acceptance: each confirmed failure has a before/after reproduction and a focused
regression for both editions where applicable. A lesson's incidental use of a
particle is not sufficient evidence to index that lesson under the particle.

## 3. Review lookup quality across all sources

- [ ] Review ambiguous generic titles and the per-record evidence in
  `website/data/popup-overrides.json`; review IMABI evidence in
  `website/data/imabi-lookups.json`.
- [ ] Check kana aliases and inflection hints for false positives as well as
  missed forms, especially ambiguous readings and verb classes.
- [ ] Review discontinuous constructions and reference-topic labels for useful
  search forms. Keep written components separate across gaps; do not create
  artificial joined words or claim arbitrary sentence parsing.
- [ ] Keep source attribution and distinct meanings intact. Aliases should make
  a source record accessible without declaring different constructions
  equivalent or implying a link-only record contains a full local explanation.

Acceptance: coverage remains complete by source-record identity, additions have
source evidence, and reviewed negative cases avoid unrelated source matches.

## 4. Preserve reproducibility and compatibility in any later release

These are follow-up gates, not an instruction to publish during this handoff.

- [ ] Build both editions from the committed snapshot using the documented
  dependencies; commit any changed inputs and update their digest locks.
- [ ] Run the relevant regression tests, then the existing artifact checks:

  ```sh
  make release
  PYTHONPATH=src python scripts/audit_popup_coverage.py
  make verify-popup
  ```

- [ ] Follow [repository publication guidance](../AGENTS.md): verify every ZIP
  footer and article heading, all previously published routes, source records,
  pinned schemas and SHA-256 checksums.
- [ ] Summarize real-app results and remaining limitations in the next proposed
  release notes. Resume implementation or publication only when requested.

Acceptance: a clean checkout with dependencies installed reproduces the pinned
assets without source acquisition or translation calls, all compatibility checks
pass, and real-app results are recorded. Any intentional source refresh is a
separate, explicit update with its input bytes, provenance and locks committed.
