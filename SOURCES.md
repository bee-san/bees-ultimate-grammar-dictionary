# Bee's Ultimate Grammar Dictionary — Source Inventory

Each edition of "Bee's Ultimate Grammar Dictionary" combines every grammar source
into one installable ZIP with unified lookup and per-source attribution. The
original and English editions are separately installable. Progressive disclosure: compact card + closed
`details` sections for the tail (readings, extra examples, provenance).

The English edition uses **GPT-6 Luna**, as requested by the user. Historical
Kanban audit workers used `global.anthropic.claude-opus-5` through Bedrock; those
audit settings do not apply to the English translation build.

## Local Anki decks (authoritative primary inputs — already on disk)

### 1. 文法.apkg  (`/home/skerraut/documents/文法.apkg`, 7.5 MB)
- Notetype: `文法 Cloze`
- 534 notes / 534 cards
- Fields: 文型, 意味, 接続, JLPTレベル, 備考,
  例文1..例文15 (Japanese example sentences, HTML with <strong> highlights),
  AI丁寧度 (AI politeness/register tag), AI例文1, AI英訳1, AI例文2, AI英訳2 (AI-generated examples w/ English)
- Rich human-written 意味/接続/備考 + up to 15 real example sentences per point.
- NOTE: fields prefixed `AI…` are AI-generated — flag/segregate per user policy
  (no LLM-generated content presented as authoritative dictionary fact; keep behind a labelled disclosure or drop).

### 2. Bunpro Grammar Reference.apkg  (`/home/skerraut/Documents/Bunpro Grammar Reference.apkg`, 257 MB)
- Notetype: `Bunpro Grammar Model Final V3`
- 964 notes / 964 cards  (large — media-heavy, 14,885 zip members)
- Fields: Grammar_Order, ID, Title, Meaning, JLPT, Structure, Nuance, Nuance_JP,
  Explanation, Explanation_JP, Rest_Examples_HTML, Front/Back (multiple cloze pairs),
  Add Reverse, Text, Back Extra, Occlusion, Image, Header
- Substantive EN + JP explanations, nuance, structure, many example sentences (Rest_Examples_HTML), images.
- User confirmed Bunpro is OK to use (prior session).

### Anki .apkg extraction notes
- `collection.anki21b` inside the .apkg is a **zstd-compressed** SQLite DB (new Anki export format).
  Decompress with python `zstandard` then open as sqlite3.
- New-Anki schema: notetypes in `notetypes` table, fields in `fields` table (ord/ntid),
  note field values in `notes.flds` split on `\x1f` (US, 0x1f).
- Media files are numbered members (`0`,`1`,...) mapped by the `media` JSON manifest member.

### 3. AIUEO JLPT Grammar.apkg
- Local input: `/home/bee/Downloads/AIUEO JLPT Grammar.apkg`, locked in `data/sources/aiueo/SOURCE.lock.json`.
- Notetype: `Aiueo-Grammar`.
- 3,806 notes: 3,805 sentence notes and one literal column-header note.
- Fields: GrammarPoint, JLPTLevel, Usage, Description, SentenceJP, SentenceEN, Audio.
- 761 grammar records, each with five Japanese examples and source-authored English translations.
- Identical headword, JLPT level, formation and bilingual description are grouped;
  different senses remain separate. HTML entity differences do not create duplicates.
- Description has Japanese prose and a `【Translation】` English counterpart. Both
  survive extraction and merge. Deck audio is not repackaged.

### English edition
- Monolingual source prose and examples without an authored English translation
  are translated by GPT-6 Luna in a separate corpus.
- Translations are labelled per source and linked to the original wording on the
  English website. Existing source-authored English takes precedence.
- Translations are keyed by input text, record kind and prompt version; incomplete
  coverage prevents publication. Normal extraction/merge builds do not call models.

## Community Yomitan dictionaries (acquired or scraped)

### DoJG — 日本語文法辞典(全集)
- Source: aiko-tanaka/Grammar-Dictionaries, `dojg/`
- Dictionary of Japanese Grammar (Basic/Intermediate/Advanced), English
- Existing Yomitan banks

### HJGP — 日本語文型辞典 (monolingual)
- Source: HuangAntimony/Nihongo-Bunkei-Jiten, pinned commit `35308928ed5cffb3a8b2f2709a54b59b896748cf`
- A Handbook of Japanese Grammar Patterns — monolingual Japanese
- 1,245 Yomitan structured-content entries with rich furigana, data-role-annotated semantic blocks
- Direct Extractor (not CommunityBankExtractor) — walks the structured content JSON tree
- Extraction: 1,245 points, 1,076 with meaning, 535 with examples, 533 with structure

### HJGP EN — 日本語文型辞典 英語版
- Source: 日本語文型辞典 bilingual Yomitan banks (A Handbook of Japanese Grammar Patterns for Teachers and Learners)
- English edition with bilingual examples (Japanese + English translations)
- CommunityBankExtractor with line-based text parsing
- Extraction: 1,049 points, 932 with examples (all with English translations)

### NINJAL — 日本語文型データベース
- Source: NINJAL (National Institute for Japanese Language and Linguistics), DOI 10.15084/0002000610
- Grammar pattern database, Japanese

### 日本語NET — JLPT文法解説まとめ
- Source: scraped from nihongokyoshi-net.com (replaces aiko-tanaka/Grammar-Dictionaries `nihongo_kyoushi/` May 2022 data)
- JLPT grammar explanations with meaning, structure, examples, English translations
- Split one bank per JLPT level (N1–N5)

### 絵でわかる日本語
- Source: aiko-tanaka/Grammar-Dictionaries, `edewakaru/`
- Grammar explained through illustrations, Japanese

### Donna Toki — どんなときどう使う 日本語表現文型辞典
- Source: donna_v1.04 Yomitan banks
- "When and How to Use" expression pattern dictionary, English/Japanese

### 毎日のんびり日本語教師 (Nihongo no Sensei)
- Source: aiko-tanaka/Grammar-Dictionaries, `nihongo_no_sensei/`
- Grammar explanations for Japanese teachers, Japanese/Chinese

### Yokubi
- Source: Morgawr/yokubi mdBook markdown
- The Common Grammar Guide (yoku.bi), English

### IMABI
- Source: imabi.org lesson pages
- Comprehensive Japanese grammar lessons (modern + classical), English

## Attribution
- Preserve per-source label on every merged entry: a statement is never detached
  from the source that made it.

## Reference data (validation gates, not dictionary content)

### KANJIDIC2 — per-kanji reading gate
- Source: KANJIDIC2, Electronic Dictionary Research and Development Group (EDRDG),
  licence CC BY-SA 4.0. https://www.edrdg.org/wiki/index.php/KANJIDIC_Project
- Used only by the reading gate (`src/bugd/readings.py`) to check that a
  contribution's `reading` is a structurally possible kana rendering of its own
  written form. It is NOT dictionary content and ships as a distilled asset, not
  the full XML.
- Distilled asset: `src/bugd/data/kanji_readings.json` (on/kun/nanori readings
  only, hiragana; 13,108 kanji). Its `_provenance` block pins the upstream XML.gz
  `sha256` and `databaseVersion`; the asset is byte-reproducible from that pinned
  source via `python scripts/distil_kanjidic.py <kanjidic2.xml.gz> src/bugd/data/kanji_readings.json`
  (stdlib-only, no third-party dependency).
- Pinned upstream: kanjidic2.xml.gz, sha256
  `dccb9cf78b3a56d139350939cec2afe4efd866eff213f9be8cd0dd5cbdcfead6`,
  database version `2026-251`.

### Headword readings — JMdict, SudachiDict, Jiten
- `website/data/headword-readings.json` gives a kana reading to each kanji
  headword that no source spells exactly. Popups print it as furigana and find
  the headword by it.
- Built by `scripts/resolve_headword_readings.py --jmdict JMdict_e.gz`, an
  acquisition step; normal builds only read the committed catalog. Each record
  keeps its evidence and the basis of its decision.
- Evidence, in order of trust: a reading the source prints beside the headword;
  JMdict's reading of the whole headword, chosen by the headword's own example
  sentences when JMdict lists several; agreement of Sudachi, Jiten and
  JMdict-per-token readings; then reviewed decisions in the script's `REVIEWED`.
- JMdict: Electronic Dictionary Research and Development Group, CC BY-SA 4.0,
  https://www.edrdg.org/jmdict/j_jmdict.html. Pinned `JMdict_e.gz` sha256
  `a84c95984295173c4a6dff2d37c16697aa7b42b469146bb0a55578d940076c5f`, created
  2026-10-07.
- SudachiPy 0.6.10 with SudachiDict-full 20260116 (Apache-2.0, Works Applications).
- Jiten (https://jiten.moe, Apache-2.0) `/api/vocabulary/parse` and word
  furigana; the responses used are committed in `data/readings/jiten-responses.json`.
- Every reading still passes the exact-spelling gate in `src/bugd/readings.py`.

### Reading corrections (UGD-11c-B)
- `data/corrections/readings.json` is an evidence-backed overlay correcting nine
  upstream publisher readings that are impossible/wrong for their written form.
  Applied deterministically at merge (contribution level, keymap-preserving),
  fail-closed if any correction matches no row. Each entry cites its evidence;
  none is invented. See the file's `_meta` block.
