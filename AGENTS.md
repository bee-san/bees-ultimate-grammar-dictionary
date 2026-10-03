# Repository guidance

## Preserve published dictionary URLs

Published article URLs are a compatibility contract. Changing them breaks links
in installed Yomitan dictionaries, including dictionaries from older releases.
Do not routinely change the hostname, repository prefix, article paths or slug
algorithm when updating content, styling, generators or hosting.

The permanent base URL is:

`https://bee-san.github.io/bees-ultimate-grammar-dictionary`

| Edition | Article path below the base URL |
| --- | --- |
| Original | `/grammar/<slug>/` |
| English | `/en/grammar/<slug>/` |

`src/bugd/site_links.py` is the shared authority for dictionary and website URLs.
The slug is the first 20 lowercase hexadecimal characters of SHA-256 over the
exact lookup expression's UTF-8 bytes. Preserve that algorithm, length, input and
trailing slash. Do not introduce normalization, titles, readings, translations,
source IDs or revision numbers into the URL. Explanation edits must leave the
address unchanged. Original dictionary entries link to original articles;
English dictionary entries link to English articles for the same expression.

If an expression is renamed, removed or merged, keep its previously published
article URL working. If a URL move is unavoidable, retain working compatibility
pages or redirects at every old address before publishing the change. Updating
only the links in new ZIPs does not repair dictionaries users already installed.
Preserve both language routes and include all source explanations on their pages.

Keep published dictionary download and update-index URLs working too. In
particular, retain the original edition's update index at
`https://raw.githubusercontent.com/bee-san/bees-ultimate-grammar-dictionary/main/dist/index.json`
and the English update index at `/downloads/index.en.json` below the site base.

## Verify publications

Build both editions with `make site` using the committed `website/data` snapshot.
Before deploying or cutting a release, inspect every term-bank entry in both
actual ZIPs: its "Read all explanations" link must equal the shared URL helper's
result for its lookup expression and edition, and that article must exist with
the correct heading. Check old published routes whenever URL generation or
lookup expressions change. Validate both ZIPs against the pinned Yomitan schemas
and publish SHA-256 checksums alongside release assets.

See `docs/website.md` for source acquisition, GPT-6 Luna translations, snapshot
refreshes and the GitHub Pages build workflow.
