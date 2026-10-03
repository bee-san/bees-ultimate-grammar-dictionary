from __future__ import annotations

import copy
import json

import pytest

from bugd.banks import build_term_entry
from bugd.english import MODEL, PROMPT_VERSION, collect_requests, english_corpus, translation_key
from bugd.model import Example, GrammarPoint
from bugd.merge import MergedEntry
from bugd.pipeline import entry_to_json
from bugd.site_links import grammar_path, grammar_url
from bugd.unify import build_contribution, contribution_from_json, contribution_to_json, to_grammar_point
from bugd.website import build_site, point_page, prose
from bugd.keymap import primary_key


def corpus():
    point = GrammarPoint(source='hjgp', source_id='1', row_uid='hjgp:1', expression='ながら',
                         meaning='二つの動作を同時に行う。', explanation='同じ人の動作に使う。',
                         examples=tuple(Example(f'例文{i}。') for i in range(9)),
                         provenance={'sourceLabel': '日本語文型辞典'})
    return {'sourceLabels': {'hjgp': '日本語文型辞典'},
            'entries': [entry_to_json(MergedEntry('ながら', contributions=[point]))]}


def translations(data):
    points = [p for entry in data['entries'] for p in entry['contributions']]
    return {'model': MODEL, 'promptVersion': PROMPT_VERSION,
            'translations': {key: 'Translated explanation.' if request['kind'] == 'definition' else 'An example sentence.'
                             for key, request in collect_requests(points).items()}}


def test_english_build_requires_every_translation_and_preserves_original_corpus():
    data = corpus()
    before = copy.deepcopy(data)
    cache = translations(data)
    output = english_corpus(data, cache)
    assert data == before
    point = output['entries'][0]['contributions'][0]
    assert point['meaning'] == 'Translated explanation.'
    assert point['examples'][0]['japanese'] == '例文0。'
    assert point['examples'][0]['english'] == 'An example sentence.'
    assert point['provenance']['englishTranslation']['original']['meaning'] == before['entries'][0]['contributions'][0]['meaning']
    del cache['translations'][translation_key('同じ人の動作に使う。')]
    with pytest.raises(ValueError, match='Missing English translation'):
        english_corpus(data, cache)


def test_authored_english_counterpart_is_kept():
    data = corpus()
    point = data['entries'][0]['contributions'][0]
    point['source'] = 'aiueo'
    point['meaning'] = 'while; at the same time'
    point['explanation'] = 'The source-authored English explanation.'
    point['explanation_ja'] = '日本語の説明。'
    output = english_corpus(data, translations(data))
    assert output['entries'][0]['contributions'][0]['explanation'] == point['explanation']


def test_bilingual_prose_and_ruby_survive_unified_round_trip():
    point = GrammarPoint(source='aiueo', source_id='1', row_uid='aiueo:1', expression='ながら',
                         explanation='While.', explanation_ja='同時。', nuance_ja='注意。',
                         examples=(Example('本。', japanese_html='<ruby>本<rt>ほん</rt></ruby>。'),))
    contribution = build_contribution('aiueo', entry_to_json(MergedEntry('ながら', contributions=[point]))['contributions'][0],
                                      canonical_key='ながら', source_label='AIUEO')
    restored = contribution_from_json(contribution_to_json(contribution))
    projected = to_grammar_point(restored, expression='ながら')
    assert projected.explanation_ja == point.explanation_ja
    assert projected.nuance_ja == point.nuance_ja
    assert projected.examples == point.examples


def test_site_and_dictionary_share_stable_links_and_full_examples(tmp_path):
    data = corpus()
    result = build_site(data, tmp_path, translations=translations(data))
    assert result['editions'] == 2
    original = (tmp_path / grammar_path('ながら') / 'index.html').read_text()
    english = (tmp_path / grammar_path('ながら', english=True) / 'index.html').read_text()
    for i in range(9):
        assert f'例文{i}。' in original
        assert f'例文{i}。' in english
    assert 'Read the original source text' in english
    assert '二つの動作を同時に行う。' in english
    row = build_term_entry(MergedEntry('ながら', contributions=[GrammarPoint('hjgp','1','ながら')]), 1)
    footer = row[5][0]['content']['content'][-1]
    assert footer['content']['href'] == grammar_url('ながら')
    search = json.loads((tmp_path / 'en' / 'search.json').read_text())
    assert search[0]['path'] == grammar_path('ながら', english=True)


def test_source_html_is_escaped_or_sanitized():
    assert '<script>' not in prose('A <script>alert(1)</script> example.')
    output = prose('<div onclick="alert(1)"><ruby>本<rt>ほん</rt></ruby></div>')
    assert 'onclick' not in output
    assert '<ruby>本<rt>ほん</rt></ruby>' in output


def test_website_keeps_every_sense_instead_of_the_popup_limit():
    data = corpus()
    entry = data['entries'][0]
    entry['contributions'] = [dict(entry['contributions'][0], source_id=str(i), row_uid=f'hjgp:{i+1}', notes=f'独立の用法{i}。') for i in range(7)]
    page = point_page(entry, data['sourceLabels'], entry, english=False)
    assert all(f'独立の用法{i}。' in page for i in range(7))


def test_alias_links_open_all_explanations_without_an_extra_click(tmp_path):
    data = corpus()
    alias = GrammarPoint('folded', 'alias', '〜ながら', provenance={'aliasOf': 'ながら'})
    data['entries'].append(entry_to_json(MergedEntry('〜ながら', contributions=[alias])))
    build_site(data, tmp_path, translations=translations(data))
    original = (tmp_path / grammar_path('〜ながら') / 'index.html').read_text()
    english = (tmp_path / grammar_path('〜ながら', english=True) / 'index.html').read_text()
    assert '二つの動作を同時に行う。' in original
    assert 'Translated explanation.' in english
    assert all(f'例文{i}。' in english for i in range(9))
    assert data['entries'][1]['contributions'][0]['meaning'] is None


def test_combined_affirmative_and_negative_heading_is_not_filed_as_the_affirmative():
    combined = primary_key({'expression': '〜に 値する・〜に 値しない'})
    assert combined != primary_key({'expression': 'に値する'})
    assert combined != primary_key({'expression': 'に値しない'})
