"""Static, searchable grammar library, generated from the complete corpus.

Pages read GrammarPoint fields directly, never the popup's bounded renderer.
All source senses and examples are rendered; unsafe source markup is converted
through the same allowlisted rich-text converter used by the dictionary.
"""

from __future__ import annotations

from collections import defaultdict
import html
import json
import pathlib
import re
import shutil
from urllib.parse import urlsplit

from .english import english_corpus
from .richtext import html_to_content
from .site_links import SITE_URL, grammar_path, grammar_slug

REPO_URL = "https://github.com/bee-san/bees-ultimate-grammar-dictionary"
ASSETS_DIR = pathlib.Path(__file__).resolve().parents[2] / "website" / "assets"
FIELD_LABELS = {"meaning": "Meaning", "structure": "How to use it", "nuance": "Nuance",
                "explanation": "Explanation", "notes": "Notes", "nuance_ja": "Nuance · 日本語",
                "explanation_ja": "Explanation · 日本語"}
TAGS = {"div", "span", "br", "ruby", "rt", "rp", "table", "thead", "tbody", "tfoot",
        "tr", "td", "th", "ul", "ol", "li", "details", "summary"}
_HAS_HTML = re.compile(r"<(?:ruby|rt|rp|span|div|p|br|strong|b|em|i|table|ul|ol|li|del|s)\b", re.I)


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def safe_url(value: object) -> str:
    if isinstance(value, str) and urlsplit(value).scheme in {"http", "https"} and urlsplit(value).netloc:
        return value
    return ""


def rich_html(node: object) -> str:
    if isinstance(node, str):
        return escape(node)
    if isinstance(node, (list, tuple)):
        return "".join(rich_html(child) for child in node)
    if not isinstance(node, dict):
        return ""
    body = rich_html(node.get("content", ""))
    tag = node.get("tag")
    if tag not in TAGS:
        return body
    if tag == "br":
        return "<br>"
    style = node.get("style") or {}
    classes = []
    if style.get("fontWeight") == "bold":
        classes.append("emphasis")
    if style.get("fontStyle") == "italic":
        classes.append("italic")
    if style.get("textDecorationLine") == "line-through":
        classes.append("omitted")
    attribute = f' class="{" ".join(classes)}"' if classes else ""
    return f"<{tag}{attribute}>{body}</{tag}>"


def prose(text: str | None) -> str:
    if not text:
        return ""
    if _HAS_HTML.search(text):
        return rich_html(html_to_content(text))
    return "".join(f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>"
                   for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip())


def grouped_entries(corpus: dict) -> dict[str, dict]:
    groups = {}
    for entry in corpus["entries"]:
        group = groups.setdefault(entry["expression"], {"expression": entry["expression"],
                                                        "variants": [], "contributions": []})
        group["variants"] = list(dict.fromkeys([*group["variants"], *entry.get("variants", [])]))
        group["contributions"].extend(entry["contributions"])
    # A dictionary alias should open the full explanation in one click, too.
    # Expand its already-resolved targets while keeping the requested spelling
    # as the page heading and address. The source corpus stays untouched.
    def resolve(expression: str, seen: frozenset[str]) -> dict:
        group = groups[expression]
        points = group["contributions"]
        expanded, variants, identities = [], list(group["variants"]), set()
        has_alias = False
        for point in points:
            target = point.get("provenance", {}).get("aliasOf")
            if target and target in groups and target not in seen | {expression}:
                resolved = resolve(target, seen | {expression})
                candidates = resolved["contributions"]
                variants.extend([target, *resolved["variants"]])
                has_alias = True
            else:
                candidates = [point]
            for candidate in candidates:
                identity = (candidate["source"], candidate.get("row_uid") or json.dumps(candidate, sort_keys=True))
                if identity not in identities:
                    expanded.append(candidate)
                    identities.add(identity)
        return dict(group, alias=has_alias and all(p.get("provenance", {}).get("aliasOf") for p in points),
                    contributions=expanded, variants=list(dict.fromkeys(variants)))
    return {expression: resolve(expression, frozenset()) for expression in groups}


def source_label(point: dict, labels: dict) -> str:
    return str(point.get("provenance", {}).get("sourceLabel") or labels.get(point["source"]) or point["source"])


def summary(entry: dict) -> str:
    meanings = [p.get("meaning") or p.get("explanation") for p in entry["contributions"]]
    candidates = [text for text in meanings if text]
    text = next((t for t in candidates if len(re.findall(r"[A-Za-z]{3,}", t)) >= 3), candidates[0] if candidates else "")
    text = re.sub(r"<[^>]+>", "", text)
    text = " ".join(html.unescape(text).split())
    if len(text) > 145:
        text = text[:142].rsplit(" ", 1)[0] + "…"
    return text or "Explore the source explanations for this grammar point."


def search_record(entry: dict, *, english: bool = False) -> dict:
    points = entry["contributions"]
    sources = list(dict.fromkeys(p["source"] for p in points if p["source"] not in {"redirect", "declared", "folded", "reading"}))
    levels = sorted({p["jlpt"] for p in points if p.get("jlpt")}, reverse=True)
    readings = list(dict.fromkeys(p["reading"] for p in points if p.get("reading")))
    terms = [entry["expression"], *entry["variants"], *readings]
    terms.extend(p.get("meaning") or "" for p in points)
    return {"expression": entry["expression"], "summary": summary(entry), "levels": levels,
            "sources": sources, "reading": " · ".join(readings), "terms": " ".join(terms),
            "alias": bool(entry.get("alias")),
            "path": grammar_path(entry["expression"], english=english)}


BEE = '<svg class="bee" viewBox="0 0 40 40" aria-hidden="true"><path d="M17 14c-9-14-17 0-6 6M23 14c9-14 17 0 6 6" fill="none" stroke="currentColor" stroke-width="2"/><ellipse cx="20" cy="24" rx="10" ry="11" fill="currentColor"/><path d="M12 20h16M11 26h18" stroke="var(--paper)" stroke-width="3"/><path d="M16 13l-3-5m11 5 3-5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'


def shell(title: str, body: str, *, root: str, path: str, english: bool,
          alternate: str, description: str = "Explore Japanese grammar with all explanations in one place.") -> str:
    home = root + ("en/" if english else "")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · Bee’s Grammar</title><meta name="description" content="{escape(description)}">
<meta name="theme-color" content="#f7f5ef"><link rel="canonical" href="{SITE_URL}/{path}">
<meta property="og:title" content="{escape(title)} · Bee’s Grammar"><meta property="og:description" content="{escape(description)}">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="{root}assets/site.css">
<script src="{root}assets/site.js" defer></script></head>
<body data-root="{root}" data-english="{'true' if english else 'false'}"><a class="skip" href="#main">Skip to content</a>
<header class="site-header"><div class="header-inner"><a class="brand" href="{home}">{BEE}<span>bee’s<span class="brand-sub">grammar dictionary</span></span></a>
<nav aria-label="Main navigation"><a href="{home}#library">The library</a><a class="sources-nav" href="{root}sources/">Our sources</a>
<a class="edition-link" href="{alternate}">{'Original sources' if english else 'English edition'} <span aria-hidden="true">↗</span></a>
<a class="download-nav" href="{home}#download">Get the dictionary <span aria-hidden="true">↓</span></a></nav></div></header>
<main id="main">{body}</main>
<footer class="site-footer"><div class="footer-inner"><a class="brand" href="{home}">{BEE}<span>bee’s<span class="brand-sub">made for the curious</span></span></a>
<p>A little more understanding, one grammar point at a time.</p><a href="{REPO_URL}">Made by Bee · GitHub ↗</a></div>
<div class="footer-credit">Explanations belong to their credited sources. {'English translations by GPT-6 Luna; originals included for reference.' if english else 'Original source text, brought together with care.'}</div></footer></body></html>'''


def card(record: dict, *, root: str = "") -> str:
    badges = "".join(f'<span class="level {level.lower()}">{level}</span>' for level in record["levels"])
    count = len(record["sources"])
    return f'''<a class="grammar-card" href="{root}{record['path']}"><div class="card-top">{badges}<span class="card-arrow" aria-hidden="true">↗</span></div>
<h3 lang="ja">{escape(record['expression'])}</h3><p class="card-reading" lang="ja">{escape(record['reading'])}</p>
<p class="card-meaning">{escape(record['summary'])}</p><div class="card-footer"><span>{count} {'sources' if count != 1 else 'source'}</span><span>Read explanations <span aria-hidden="true">→</span></span></div></a>'''


def homepage(records: list[dict], labels: dict, example_count: int, *, english: bool) -> str:
    root = "../" if english else ""
    options = "".join(f'<option value="{escape(name)}">{escape(label)}</option>' for name, label in sorted(labels.items(), key=lambda x: x[1]))
    initial = "".join(card(record, root=root) for record in records[:36])
    title = "Grammar, in<br><em>plain English.</em>" if english else "Small particles.<br><em>Big possibilities.</em>"
    intro = ("Every source. Every explanation. Now in English, with the original Japanese close at hand."
             if english else "The Japanese grammar library you’ll keep coming back to. All your favourite explanations, together in one thoughtful place.")
    notice = '<p class="translation-note">English edition · Translated with GPT-6 Luna. Original text included.</p>' if english else ''
    body = f'''<section class="hero wrap"><div class="hero-copy"><div class="eyebrow"><span class="small-dot"></span> A FIELD GUIDE TO JAPANESE</div>
<h1>{title}</h1><p class="hero-description">{intro}</p>{notice}<a class="primary" href="#library">Find a grammar point <span aria-hidden="true">↗</span></a>
<div class="hero-stats"><div><strong>{len(records):,}</strong><span>lookup forms</span></div><div><strong>{len(labels)}</strong><span>grammar sources</span></div><div><strong>{example_count:,}</strong><span>examples to explore</span></div></div></div>
<div class="hero-art" aria-hidden="true"><div class="art-grid"></div><span class="art-note">a little particle, a whole new meaning</span>
<div class="paper-back"><span lang="ja">日本語の、<br>なるほど。</span></div><div class="paper-front"><div class="paper-meta"><span>GRAMMAR FIELD NOTES</span><span class="level n4">N4</span></div>
<div class="paper-word" lang="ja">ながら<span>nagara</span></div><div class="paper-line"></div><p>while; at the same time</p>
<div class="paper-example" lang="ja">音楽を聞き<span>ながら</span><br>日本語を勉強する。</div><p class="paper-translation">Studying Japanese while listening to music.</p>
<div class="paper-bottom"><span>One point. Many perspectives.</span><span>↗</span></div></div><span class="art-star">✳</span></div></section>
<div class="library-band"><span>ONE LOOKUP. ALL THE EXPLANATIONS.</span><span lang="ja">文法がわかると、日本語がもっと楽しくなる。</span><span class="band-flower">✳</span></div>
<section class="library wrap" id="library"><div class="section-heading"><div class="eyebrow">THE GRAMMAR LIBRARY</div><h2>Find your next <em>“aha”.</em></h2><p>Look up a particle, explore a pattern, or see what clicks.</p></div>
<form class="search-form" role="search"><label class="sr-only" for="grammar-search">Search grammar, meaning or reading</label><span class="search-icon" aria-hidden="true">⌕</span>
<input id="grammar-search" name="q" type="search" placeholder="Search grammar, meaning or reading…" autocomplete="off"><kbd aria-hidden="true">/</kbd></form>
<div class="filters"><div class="level-filters" role="group" aria-label="Filter by JLPT level"><button type="button" class="active" data-level="" aria-pressed="true">All levels</button>
{''.join(f'<button type="button" data-level="{level}" aria-pressed="false">{level}</button>' for level in ('N5','N4','N3','N2','N1'))}</div>
<label class="source-filter">Source <select id="source-filter"><option value="">All sources</option>{options}</select></label></div>
<div class="results-heading"><p id="result-count" role="status" aria-live="polite">{len(records):,} grammar entries</p><span>Something new to understand.</span></div>
<div class="grammar-grid" id="grammar-results">{initial}</div><div id="search-empty" class="empty-state" hidden><span>✳</span><h3>No grammar points found</h3><p>Try a shorter form, an English meaning, or a different filter.</p><button type="button" id="clear-filters">Clear search &amp; filters</button></div>
<p id="search-error" class="search-error" role="alert" hidden>Search could not load. <button type="button" id="retry-search">Try again</button></p>
<button class="load-more" type="button" id="load-more" hidden>Explore more grammar <span aria-hidden="true">↓</span></button><noscript><p>Enable JavaScript to search and filter the complete library.</p></noscript></section>
<section class="download wrap" id="download"><div><div class="eyebrow">TAKE THE LIBRARY WITH YOU</div><h2>A little grammar,<br><em>wherever you read.</em></h2><p>Import Bee’s into Yomitan for quick explanations as you read. Every entry links back here for the full picture.</p></div>
<div class="download-options"><a class="primary" href="{root}downloads/bees-ultimate-grammar-dictionary{'-en' if english else ''}.zip">Download {'English ' if english else ''}dictionary <span aria-hidden="true">↓</span></a>
<a class="text-link" href="{root}downloads/bees-ultimate-grammar-dictionary{'-en' if not english else ''}.zip">Or get the {'English' if not english else 'original'} edition →</a><p>Yomitan settings → Dictionaries → Import</p></div></section>'''
    return shell("English Grammar Library" if english else "Japanese Grammar Library", body, root=root,
                 path="en/" if english else "", english=english, alternate=root if english else "en/")


def fields_html(point: dict) -> str:
    sections = []
    seen = set()
    for field, label in FIELD_LABELS.items():
        text = point.get(field)
        if not text or text in seen:
            continue
        seen.add(text)
        lang = 'ja' if field.endswith('_ja') or not re.search(r'[A-Za-z]{3,}', text) else 'en'
        sections.append(f'<div class="definition-field"><h4>{label}</h4><div class="source-prose" lang="{lang}">{prose(text)}</div></div>')
    return "".join(sections)


def examples_html(examples: list[dict]) -> str:
    human = [example for example in examples if not example.get("ai_generated")]
    if not human:
        return ""
    items = []
    for example in human:
        japanese = prose(example.get("japanese_html") or example["japanese"])
        translation = f'<p class="example-english" lang="en">{escape(example["english"])}</p>' if example.get("english") else ""
        items.append(f'<li><div class="example-japanese" lang="ja">{japanese}</div>{translation}</li>')
    return '<div class="examples"><h4>In context <span>' + str(len(items)) + ' examples</span></h4><ol>' + "".join(items) + '</ol></div>'


def point_page(entry: dict, labels: dict, original: dict, *, english: bool) -> str:
    root = "../../../" if english else "../../"
    home = root + ("en/" if english else "")
    points_by_source = defaultdict(list)
    for point in entry["contributions"]:
        points_by_source[point["source"]].append(point)
    original_points = {p.get("row_uid") or p["source_id"]: p for p in original["contributions"]}
    toc, sections = [], []
    for source, points in points_by_source.items():
        label = source_label(points[0], labels)
        toc.append(f'<a href="#source-{escape(source)}">{escape(label)}</a>')
        senses = []
        for index, point in enumerate(points, 1):
            translation = point.get("provenance", {}).get("englishTranslation")
            translation_badge = '<span class="translation-badge">Luna English translation</span>' if translation else ''
            level = f'<span class="level {point["jlpt"].lower()}">{point["jlpt"]}</span>' if point.get("jlpt") else ''
            explanation = fields_html(point)
            alias = point.get("provenance", {}).get("aliasOf")
            if not explanation and alias:
                explanation = f'<p>See <a href="{root}{grammar_path(str(alias), english=english)}" lang="ja">{escape(alias)}</a> for this form’s explanations.</p>'
            if not explanation and not point.get("examples"):
                explanation = '<p>This source lists the form without an explanation.</p>'
            original_point = original_points.get(point.get("row_uid") or point["source_id"], point)
            original_disclosure = f'<details class="original"><summary>Read the original source text</summary>{fields_html(original_point)}</details>' if translation else ''
            lesson_title = point.get("provenance", {}).get("lessonTitle") if source == "imabi" else None
            heading = (f'<h3 class="sense-heading">{escape(lesson_title)}</h3>' if lesson_title else
                       f'<h3 class="sense-heading">Usage {index}</h3>' if len(points) > 1 else '')
            lesson_url = safe_url(point.get("provenance", {}).get("lessonUrl")) if lesson_title else ''
            if lesson_url:
                heading += f'<a class="upstream-link" href="{escape(lesson_url)}" rel="noreferrer">Read this IMABI lesson ↗</a>'
            senses.append(f'<div class="sense">{heading}<div class="sense-meta">{level}{translation_badge}</div>{explanation}{examples_html(point.get("examples", []))}{original_disclosure}</div>')
        provenance = points[0].get("provenance", {})
        links = [provenance.get("url"), provenance.get("lessonUrl"), provenance.get("pageUrl"), *provenance.get("producerLinks", [])]
        upstream = next((safe_url(link) for link in links if safe_url(link)), '')
        link = f'<a class="upstream-link" href="{escape(upstream)}" rel="noreferrer">Visit source ↗</a>' if upstream else ''
        sections.append(f'<section class="source-section" id="source-{escape(source)}"><div class="source-heading"><div><span class="source-number">{len(sections)+1:02}</span><h2>{escape(label)}</h2></div>{link}</div>{"".join(senses)}</section>')
    record = search_record(entry, english=english)
    badges = "".join(f'<span class="level {level.lower()}">{level}</span>' for level in record["levels"])
    variants = ', '.join(entry['variants'])
    body = f'''<div class="entry-wrap wrap"><a class="back-link" href="{home}#library">← Back to the library</a><div class="entry-intro"><div class="eyebrow">A CLOSER LOOK</div>
<h1 lang="ja">{escape(entry['expression'])}</h1>{f'<p class="entry-reading" lang="ja">{escape(record["reading"])}</p>' if record['reading'] else ''}
<p class="entry-meaning">{escape(record['summary'])}</p><div class="entry-meta">{badges}<span>{len(points_by_source)} source perspectives</span>{'<span class="translation-badge">English edition</span>' if english else ''}</div>
{f'<p class="variants">Also found as <span lang="ja">{escape(variants)}</span></p>' if variants else ''}</div>
<div class="entry-layout"><article class="entry-content">{''.join(sections)}</article><aside class="entry-sidebar"><div class="toc"><span class="eyebrow">IN THIS ENTRY</span>{''.join(toc)}<div class="toc-note">One grammar point, different perspectives. Each explanation keeps its own source.</div>
<button type="button" id="furigana-toggle" aria-pressed="false">Hide furigana</button></div></aside></div></div>'''
    return shell(entry['expression'], body, root=root, path=grammar_path(entry['expression'], english=english),
                 english=english, alternate=root + grammar_path(entry['expression'], english=not english), description=record['summary'])


def build_site(corpus: dict, output: pathlib.Path, *, translations: dict | None = None) -> dict:
    if not corpus.get("entries"):
        raise ValueError("Refusing to publish an empty grammar library")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ASSETS_DIR, output / "assets", dirs_exist_ok=True)
    labels = corpus.get("sourceLabels", {})
    original = grouped_entries(corpus)
    editions = [(False, corpus)]
    if translations is not None:
        editions.append((True, english_corpus(corpus, translations)))
    pages = []
    for english, edition in editions:
        groups = grouped_entries(edition)
        records = [search_record(entry, english=english) for entry in groups.values()]
        records.sort(key=lambda r: (r['alias'], -len(r['sources']), r['expression']))
        base = output / ("en" if english else "")
        base.mkdir(parents=True, exist_ok=True)
        (base / "search.json").write_text(json.dumps(records, ensure_ascii=False, separators=(",", ":")))
        example_count = sum(sum(not ex.get("ai_generated") for ex in p.get("examples", []))
                            for entry in edition["entries"] for p in entry["contributions"])
        (base / "index.html").write_text(homepage(records, labels, example_count, english=english))
        pages.append("en/" if english else "")
        for expression, entry in groups.items():
            path = grammar_path(expression, english=english)
            directory = output / path
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "index.html").write_text(point_page(entry, labels, original[expression], english=english))
            pages.append(path)
    sources = ''.join(f'<li><h2>{escape(label)}</h2><p>{sum(p["source"] == source for entry in corpus["entries"] for p in entry["contributions"]):,} attributed contributions</p></li>' for source, label in sorted(labels.items()))
    (output / "sources").mkdir(exist_ok=True)
    (output / "sources" / "index.html").write_text(shell('Our sources', f'<section class="sources-page wrap"><div class="eyebrow">MANY PERSPECTIVES, ONE LIBRARY</div><h1>A good explanation<br><em>starts somewhere.</em></h1><p>Every explanation and example keeps the source it came from. Different sources may describe different senses or assign different JLPT levels; those distinctions remain visible.</p><ul class="sources-list">{sources}</ul><a class="text-link" href="{REPO_URL}/blob/main/SOURCES.md">Read the complete source inventory ↗</a></section>', root='../', path='sources/', english=False, alternate='../en/'))
    (output / '404.html').write_text(shell('Page not found', '<section class="sources-page wrap"><div class="eyebrow">A SMALL DETOUR</div><h1>Let’s find<br><em>your grammar point.</em></h1><p>This page could not be found.</p><a class="primary" href="/bees-ultimate-grammar-dictionary/#library">Search the library →</a></section>', root='/bees-ultimate-grammar-dictionary/', path='404.html', english=False, alternate='/bees-ultimate-grammar-dictionary/en/'))
    sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{SITE_URL}/{path}</loc></url>' for path in [*pages, 'sources/']) + '</urlset>'
    (output / 'sitemap.xml').write_text(sitemap)
    (output / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n')
    (output / '.nojekyll').touch()
    return {'grammarForms': len(original), 'editions': len(editions), 'pages': len(pages), 'sources': len(labels)}
