import pytest

from bugd.sources.hjgp import _XREF as JA_XREF
from bugd.sources.hjgp_en import HjgpEnExtractor
from bugd.sources.yomitan_bank import TermRow


@pytest.mark.parametrize('text,target', [('参照⇾せられたい','せられたい'), ('参照⇾きわまりない','きわまりない'), ('⇾【ぶり】','ぶり')])
def test_monolingual_crossreference_keeps_complete_target(text, target):
    assert JA_XREF.search(text).group(1).strip().strip('【】') == target


def test_bilingual_crossreference_keeps_full_word_and_removes_sense_number(tmp_path):
    row = TermRow(expression='久しぶり', reading='ひさしぶり', definition_tags='',
                  deinflectors='', text='参照⇾ぶり２', sequence=1, term_tags='')
    point = HjgpEnExtractor(tmp_path).parse(row)
    assert point.provenance['aliasOf'] == 'ぶり'
