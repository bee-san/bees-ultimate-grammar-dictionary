# Grammar library and English edition

The website and Yomitan dictionaries share stable, SHA-256-derived addresses for
each written lookup form. Pages contain the full corpus, including all senses and
examples; the popup's four-sense and six-example display budgets do not apply.
English pages use the same addresses under `/en/`. Each English dictionary card
links to its English page. The original edition links to the original page.

The site is static HTML/CSS/JavaScript. Entry explanations work without JavaScript;
the library search loads a compact index and supports meaning, reading, JLPT and
source filters. All paths work beneath the repository's GitHub Pages prefix.

## Build a published snapshot

```sh
python3 -m pip install .
make site
python3 -m http.server 8000 --directory build/site
```

`website/data/manifest.json` pins the compressed corpus, translation cache and
IMABI lookup catalog by
SHA-256 and byte count. `scripts/build_site.py` checks those digests, refuses an
empty corpus or incomplete translation cache, generates both sites, and builds
and schema-validates both downloadable Yomitan ZIPs. Source content is attributed
on every page and retains its original licensing.

The Pages workflow builds from this snapshot rather than scraping or invoking a
model in CI. Enable GitHub Pages with **GitHub Actions** as its source. Pushes to
`main` deploy automatically; pull requests build without deploying.

## Refresh content

1. Acquire the exact source bytes pinned by `data/sources/*/SOURCE.lock.json`.
   Local Anki packages may be symlinked into their source directories. For AIUEO,
   use `data/sources/aiueo/AIUEO JLPT Grammar.apkg`.
2. Run `make all` to extract, align, merge and validate the complete corpus.
3. Run `make translate-english`. This calls the authenticated `codex exec` CLI
   with `--model gpt-6-luna`. No API key is stored in the repository. Jobs receive
   only translation input, use a JSON output schema, and validate every returned
   record id before caching the result. Re-running resumes by content hash.
4. Run `make publish-data` to update the compressed publication snapshot. It
   requires every registered source and every requested English translation.
5. Run `make site`, inspect both editions in a browser, then commit the changed
   snapshot, manifests and code. The next Pages deployment rebuilds them.

The generated output lives under `build/site/`. Dictionary downloads and their
SHA-256 checksums are in `build/site/downloads/`. The English archive has its own
dictionary title and update index, so the two editions can be installed together.

## Translation policy

Source-authored English is used whenever supplied. Mono Japanese/Chinese prose
and missing example translations are translated faithfully with GPT-6 Luna.
Grammar forms, construction formulas, omissions, negation and register are
preserved. AI-generated example channels from the original sources remain
separate. Translation provenance is stored beside each transformed contribution;
the source corpus is not overwritten. English pages include expandable original
definitions, and Japanese example sentences remain visible with their readings.

Coverage and schema checks establish completeness and structure, not a human
review of every translated sentence. Readers can compare the original wording
through each page's disclosure or switch to the original edition.

## Reproducible releases

`make` (or `make release`) builds both full editions from the committed snapshot
and verifies the release. `website/data/release.json` pins the exact archive and
index bytes. Verification also reads every committed IMABI file through its
digest lock, accounts for every lesson, checks all 13 sources, validates both
archives against the pinned Yomitan schemas, and checks every article link and
heading in both editions.

Verification checks every source record's Japanese lookup terms for a rendered
source disclosure in each actual ZIP and its complete record on the full
article. It also preserves all 6,408 previously published written headwords,
including the Japanese aliases introduced by the previous IMABI release.

### IMABI lookup indexing

The older corpus used English lesson titles as IMABI headwords. The committed
`imabi-lookups.json` indexes all 495 lessons under 1,400 Japanese forms and topic
labels, using titles, section headings, constructions and readings. Forms in examples
are not harvested indiscriminately. Optional forms and combined headings are
expanded explicitly in the catalog, with evidence retained for review.

`bugd.imabi_lookup.apply_lookups` adds the lesson contributions after cross-source
alignment. A link means that the article discusses a form; it does not assert
that all forms in the article are equivalent. It keeps each lesson's full text,
identity and attribution, and retains every original entry and article URL.
The same projection runs for acquired-source and snapshot builds. Applying it
twice has no effect. The base compressed corpus and translation cache remain
unchanged. The manifest explicitly restores lesson 535 ("About") from the locked
raw source before indexing, preserving every existing source-record identity.
Its 38 examples already have source-authored English translations.

Multiple IMABI articles are labelled by lesson title. The popup shows up to four
lessons and notes when more are available; the linked article includes them all.
Broad lessons about pronunciation, writing or vocabulary use Japanese topic
labels, so they can be found without knowing an English lesson title.

### All-source popup indexing

`bugd.popup_lookup` adds literal lookup aliases after source alignment. It removes
placeholder and sense notation, expands alternatives and optional particles,
and uses the longest literal component of discontinuous patterns. It never
joins words across a wildcard. Strict whole-spelling checks prevent malformed
source readings from becoming aliases.

`popup-overrides.json` holds reviewed row-specific constructions for ambiguous
titles. Source IDs, meanings and structures guard the evidence against drift.
Publication fails if a source record has no Japanese form. Partial acquisition
builds retain new, unreviewed source records for subsequent catalog review.
Known literal endings receive conservative Yomitan conjugation classes.

See [coverage and hover examples](lookup-coverage.md). Run
`PYTHONPATH=src python scripts/audit_popup_coverage.py` for current per-source
counts, and `make verify-popup` with Node.js 24 for sentence/cursor tests against
both ZIPs using the committed, digest-pinned upstream Yomitan engine.

To edit the catalog, review the corresponding locked `pages/<id>.json`, keep its
exact title and heading evidence, then update the catalog digest and effective
entry count in `manifest.json`. Extraction fails if the evidence no longer
matches the acquired page. Use a new revision and regenerate the release lock
with the publication commands below.

The IMABI raw pages are an independently locked acquisition. The merged
publication snapshot also retains earlier normalization, deduplication and
corrections across all sources; rebuilding a release uses that snapshot rather
than rerunning acquisition against changing upstream websites.

When updating the publication, choose a new revision in `manifest.json`, run
`make site`, copy `build/site/downloads/index.json` to `dist/index.json`, then run
`PYTHONPATH=src python scripts/verify_release.py --write-lock`. Review the
output, run `make verify-release` and `make verify-popup`, and commit all changed inputs with notes at
`docs/releases/v<revision>.md`. A push of the revised snapshot to `main` triggers
the release workflow, which builds and verifies before uploading both ZIPs,
both indexes and `SHA256SUMS`. A workflow dispatch can retry a failed release.
