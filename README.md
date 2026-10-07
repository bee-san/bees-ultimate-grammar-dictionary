# Bee's Ultimate Grammar Dictionary

13 Grammar Dictionaries in one
<img width="849" height="361" alt="image" src="https://github.com/user-attachments/assets/06c86e75-4dd3-4a0d-8862-b3007b0c61ae" />


## Install

1. Download the [dictionary ZIP](https://bee-san.github.io/bees-ultimate-grammar-dictionary/downloads/bees-ultimate-grammar-dictionary.zip)
2. In Yomitan settings, go to Dictionaries → Import
3. Select the downloaded ZIP

You can also [browse the grammar library](https://bee-san.github.io/bees-ultimate-grammar-dictionary/)
or use the [English website](https://bee-san.github.io/bees-ultimate-grammar-dictionary/en/).
Every dictionary entry links to its page, with all contributing explanations and
examples. Search by grammar, reading or meaning, and filter by JLPT level or source.

Japanese popup lookup covers **all 9,152 source records** across the 13 sources.
Grammar notation such as `Nらしい` is indexed under its Japanese text (`らしい`),
with kana aliases and conjugation support for known endings. Reference articles
use Japanese topic names. See [lookup coverage and examples](docs/lookup-coverage.md).

The [English Yomitan edition](https://bee-san.github.io/bees-ultimate-grammar-dictionary/downloads/bees-ultimate-grammar-dictionary-en.zip)
is separately installable. Monolingual explanations and untranslated examples are
translated with **GPT-6 Luna** and labelled as translations. Source-authored English
is retained. The English website includes the original source text for reference.

## What's included

Every grammar point shows a compact card with progressive disclosure — click to expand per-source details, extra examples, and provenance.

### Sources

| Source | Name | Language | Description |
|--------|------|----------|-------------|
| DoJG | 日本語文法辞典(全集) | EN | Dictionary of Japanese Grammar (Basic/Intermediate/Advanced) |
| HJGP | 日本語文型辞典 | JA | A Handbook of Japanese Grammar Patterns — monolingual |
| HJGP EN | 日本語文型辞典 英語版 | EN | A Handbook of Japanese Grammar Patterns — English edition |
| NINJAL | 日本語文型データベース | JA | National Institute for Japanese Language and Linguistics grammar pattern database |
| 日本語NET | JLPT文法解説まとめ | JA | JLPT grammar explanations from nihongokyoshi-net.com |
| 絵でわかる | 絵でわかる日本語 | JA | Japanese grammar explained through illustrations |
| Donna Toki | どんなときどう使う 日本語表現文型辞典 | EN/JA | "When and How to Use" expression pattern dictionary |
| 日本語教師 | 毎日のんびり日本語教師 | JA/ZH | Grammar explanations for Japanese teachers |
| Bunpro | Bunpro Grammar Reference | EN | SRS-based grammar reference |
| 文法 | 文法 | JA | Personal grammar Anki deck |
| IMABI | IMABI | EN | Comprehensive Japanese grammar lessons (modern + classical) |
| Yokubi | Yokubi | EN | The Common Grammar Guide (yoku.bi) |
| AIUEO | AIUEO JLPT Grammar | EN/JA | 761 grammar records with 3,805 bilingual examples from the AIUEO Anki deck |

### What makes this different from installing them separately?

- **Single lookup**: one dictionary, one card per grammar point — not 13 separate popups
- **Merged entries**: when multiple sources describe the same grammar point, their contributions are merged into one card with per-source attribution
- **Deduplication**: the keymap stage aligns entries across sources so you don't see the same point repeated
- **Progressive disclosure**: compact by default, expand any source's details on demand

## Building from source

```
python3 -m venv .venv
source .venv/bin/activate
pip install .
make
```

The default build recreates **both full 13-source editions** from the committed
corpus and English translation cache, checks their pinned asset digests, and
verifies every dictionary-to-article link. It needs no source downloads, Anki
exports, scraper access or model credentials. The ZIPs, update indexes and
`SHA256SUMS` are written to `build/site/downloads/`.

The raw 501-page IMABI acquisition is also committed under
`data/sources/imabi/`, together with its digest lock, index and coverage report.
It contains 495 lessons; six site pages are excluded. The publication snapshot
preserves the complete merged corpus from every source, including the source
decks that are unavailable in a fresh checkout.

IMABI lessons are also indexed by Japanese grammar forms, so looking up `は`,
`に`, `を`, `けど` or `のだ` shows the relevant IMABI articles. The committed
`website/data/imabi-lookups.json` maps **495 lessons to 1,400 Japanese lookup
terms**, using their titles, headings, constructions, readings and topic labels.
Multiple lessons keep their own titles and explanations. Original article
addresses remain available; the linked website includes every matching lesson.
This includes the restored “About” lesson under `について`, `に関して` and
`をめぐって`, plus compound constructions such as `ことにする` and `ことがある`.

To refresh the corpus from original inputs, acquire any missing sources and run
`make all`. Those pipeline stages are:

1. **extract** — read each source's locked data into normalized `GrammarPoint` records
2. **keymap** — align entries across sources (which rows are the same grammar point?)
3. **merge** — combine aligned entries into a unified dataset
4. **build** — render the Yomitan dictionary ZIP
5. **validate** — verify against Yomitan's JSON schemas

### Website and English edition

The committed publication snapshot makes both websites and dictionary downloads
reproducible without local source decks, network scraping, or model credentials:

```sh
make site
python3 -m http.server 8000 --directory build/site
```

Open `http://localhost:8000/` or `http://localhost:8000/en/`.
GitHub Actions builds this snapshot and deploys it to GitHub Pages on `main`.
See [the publishing workflow](docs/website.md) for updating the corpus and translations.

After acquiring all locked sources and running `make all`, update the publication:

```sh
make translate-english  # authenticated Codex CLI; explicitly uses gpt-6-luna
make publish-data      # refuses missing sources or translations
make site
```

After refreshing the snapshot, bump its revision, run `make site`, regenerate
the release asset lock with `python scripts/verify_release.py --write-lock`,
and run `make verify-release`. Commit the snapshot, lock and release notes.
The release workflow builds and checks those exact inputs before publishing.

Translation results are cached by source-text hash under `data/translations/`.
The original corpus stays unchanged. A changed source text requires a fresh
translation; an incomplete English edition fails the build.

## Adding a new source

1. Place source data in `data/sources/<name>/` with a `SOURCE.lock.json`
2. Write an extractor in `src/bugd/sources/<name>.py` (see existing extractors for patterns)
3. Register it with `@register_extractor`
4. Add to `SOURCE_PRECEDENCE` in `keymap.py` and `_SOURCE_EXPLANATION_LANG` in `banks.py`
5. Run `make all`

## License

Dictionary content retains its original licensing from each source. The build pipeline code is MIT.
