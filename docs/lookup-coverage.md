# Japanese popup lookup coverage

Release `v2026.10.07.2` gives every one of the **9,152 source records** at least
one Japanese lookup form. Both editions have **7,640 term-bank rows**, including
the original titles and notation preserved for compatibility. Source records
are counted once by their stable identity, regardless of how many aliases they
have; term-bank rows are lookup entries, not separate lessons.

| Source | Records | Records with Japanese lookups |
| --- | ---: | ---: |
| AIUEO | 761 | 761 |
| 文法 | 534 | 534 |
| Bunpro | 964 | 964 |
| DoJG | 534 | 534 |
| Donna Toki | 660 | 660 |
| 絵でわかる | 1,178 | 1,178 |
| HJGP | 924 | 924 |
| HJGP English | 932 | 932 |
| IMABI | 495 | 495 |
| 日本語NET | 505 | 505 |
| 毎日のんびり日本語教師 | 733 | 733 |
| NINJAL | 800 | 800 |
| Yokubi | 132 | 132 |
| **Total** | **9,152** | **9,152** |

## What changed

- Placeholder labels (`Nらしい`, `AながらB`), sense numbers and optional notation
  have literal Japanese aliases. Discontinuous patterns such as `ば〜ほど` use
  the meaningful written segment (`ほど`), without joining text across a gap.
- Ambiguous English labels use reviewed source-record overrides. Bunpro's
  different `Verb[て]` records teach different things: the negative-request
  record now appears under `ないで`, while the causative record uses `させる`.
- Kana readings become aliases only when the full written form matches. This
  rejects truncated readings and readings that join multiple alternatives.
- All 495 IMABI lessons have Japanese forms or topic labels, with 1,400 distinct
  terms and 1,677 lesson-to-term links. Explicit compound constructions are
  indexed too: `ことにする`, `ことがある`, `のみならず`, `までもない`, etc.
- IMABI page 535, “About,” is a grammar lesson, not an information page. Its
  complete text and 38 bilingual examples are restored from the locked raw
  page, under `について`, `に関して`, `をめぐって` and related spellings.
- A row's reading is used only when it is an exact kana spelling of its
  headword. Popups print the reading as furigana and also match hovered text by
  it, so a notation, joined or truncated reading is dropped. A kana headword
  is also found by its producer's own lookup key (`たかが` for `たかがく`).
- Negative constructions filed under synthetic affirmative lemmas (`ずにはいる`,
  `もする`, `ねばなる`) appear under their real forms. The lemma rows, typo rows
  (`と言いえ`) and corrupted rows (`と言ではない`) remain for their published
  URLs. Conjugation and reading lookups cannot reach them.
- Known verb and adjective endings carry Yomitan conjugation classes. This lets
  forms such as `すぎた`, `にくかった`, `込んだ` and `ことにした` find their lemmas.
- Every source disclosure says when further explanations are on the linked
  article. Full articles retain every matched source record and its identity.
- HJGP articles stored in a `meaning` field now get their own popup disclosure;
  another source's compact headline no longer hides them. Source records that
  originally supplied only a page link are explicitly marked as listings, with
  their individual source-page links on the full article.

## Try it

Update or reimport the dictionary in Yomitan. Hover the indicated part of these
sentences; both editions should return the listed entry and source.

| Sentence | Hover | Entry | Source |
| --- | --- | --- | --- |
| これは便利です。 | は | は | IMABI |
| 政治について話す。 | について | について | IMABI |
| 食べすぎた。 | すぎた | すぎる | IMABI |
| 歩きにくかった。 | にくかった | にくい | IMABI |
| 飛び込んだ。 | 込んだ | 込む | IMABI |
| 毎日読むことにした。 | ことにした | ことにする | IMABI |
| 学生らしかった。 | らしかった | らしい | Bunpro |
| 行かないで。 | ないで | ないで | Bunpro |
| 笑わずにはいられなかった。 | ずには | ずにはいられない | どんなとき |
| 学生とはいえ、 | とはいえ | とはいえ | どんなとき |
| 天才と言っても過言ではない。 | と言っても | と言っても過言ではない | NINJAL |

The coverage claim is **findability by Japanese form or topic**, not automatic
recognition of every sentence construction. For discontinuous grammar, hover
its written particle or ending. Pronunciation, writing, conjugation-reference
and vocabulary lessons use topic queries such as `母音`, `古典文法` or `接尾辞`;
these do not match every example word in the lesson. Popup matching also depends
on where the cursor starts and the reader's scanning settings. The dictionary
does not parse arbitrary gaps between words, nor does its alias catalog replace
a full vocabulary dictionary.

## Reproduce the checks

```sh
make                         # Both full editions, schemas, source coverage and article links
PYTHONPATH=src python scripts/audit_popup_coverage.py
make verify-popup            # Node.js 24; no npm install or network required
```

`verify_release.py` reads both actual ZIPs and checks each planned lookup's
source disclosure and full article record, every footer URL and heading, and
all 6,408 previously published headwords in both language routes. It checks
source digests, schemas and release checksums too.

`verify-popup` tests 19 sentence/cursor cases per ZIP using the unmodified,
digest-pinned Yomitan Japanese transformation engine, including its POS filter.
It also checks 4 cases where a synthetic lemma such as `ずにはいる` must not match.
The engine is committed under `tests/vendor/yomitan` with its upstream licence.
This tests lookup mechanics against packaged data; it is not a browser UI test.

The raw IMABI corpus, complete frozen source corpus, English translation cache,
lookup catalogs, overrides and compatibility headwords are all committed. A
normal release build requires no scraping or translation calls.

## Follow-up work

See [the popup lookup handoff and next steps](popup-lookup-next-steps.md) for
real-app validation, reported-miss triage and acceptance criteria for later work.
