"""Conservative Yomitan POS hints for known inflecting grammar endings.

Only literal Japanese headwords qualify. Never guess the class of an arbitrary
る-ending verb or an arbitrary い-ending noun. Longest known suffix wins.
"""
from .popup_lookup import is_japanese_form

ENDINGS = {
    "v1": "いる みる 見る あげる 上げる くれる 呉れる られる れる させる せる すぎる 過ぎる かねる 兼ねる できる 出来る きれる 切れる 続ける つづける 始める はじめる 終える おえる 得る える つける 付ける かける 掛ける 向ける みせる 見せる そびれる 遅れる 忘れる おそれる 恐れる 絶える 耐える 堪える 加える 比べる 決める 求める 認める 備える 触れる 受ける 受け入れる 入れる 落ちる 生きる 信じる 通じる 応じる 禁じる 命じる 感じる 存じる 用いる 述べる 思える 言える いえる",
    "v5": "ある 有る なる 成る なさる くださる 下さる いらっしゃる おっしゃる 仰る ござる しまう 終わる おわる もらう 貰う いく 行く ゆく 置く おく 書く 読む 言う いう 思う 合う あう 切る きる 入る はいる 要る 参る まいる 帰る かえる 込む こむ 出す だす がる 違う 従う 伴う 通す 過ごす 済む すむ すます 済ます 尽くす 押す 押し切る 負う 頼る 当たる 渡る 渡す 及ぶ 抜く 届く 立つ 直す 寄る よる やる",
    "vs": "する",
    "vk": "くる 来る",
    "adj-i": "ない 無い たい にくい 難い がたい づらい 辛い やすい 易い らしい ほしい 欲しい っぽい よい 良い いい よろしい 多い 少ない すごい 凄い 悪い 大きい 小さい 高い 低い 強い 弱い 深い 浅い 早い 遅い 新しい 古い 長い 短い 憎い やむを得ない",
}
# Other attested literal verb endings in the publication. Inflected labels
# (ます, でしょう, etc.) and classical-only auxiliaries are not modern lemmas.
ENDINGS["v1"] += " あぐねる あらためる おりる くらべる こける しめる てのける でる おける たりる 準じる 足りる ふざける 下げる 倦ねる 出る 損じる 損ねる 改める 於ける 果てる 演じる 着る 立てる 負ける 閉じる 変える 垂れる してる てる たげる びる"
ENDINGS["v5"] += " いたす いただく いたる おもう おる おろす かえす かかる かぎる かく かす かぶる がかる きく きわまる ぐむ こなす さす しぶる しる じゃう そこなう ちゃう つくす つづく たまる てく てまう とおす とく ともなう どく なおす ながす なす かかわる かわる つく さきだつ ともなう まつわる もとづく わたる 基づく 沿う 至る 足る 関わる 限る ぬく ぬらす ねがう ぶる まわる むく めく やぐ やむ ゆう よごす らぐ わかる たどる 付く 伺う 依る 倦む 催す 働く 分かる 古す 向く 吹く 喜ぶ 回す 回る 垂らす 増す 変わる 嫌う 定まる 履く 巡る 巻く 引く 張る 怒る 急ぐ 成す 始まる 振る 捕まる 捲る 掛かる 損なう 果たす 極まる 止む 残す 殴る 気づく 求まる 汚す 決まる 活かす 渋る 漏らす 濡らす 穿く 結ぶ 続く 陥る 脱ぐ 腐る 致す 落とす 見つかる 触る 誤る 返す 返る 逃す 遊ぶ 運ぶ 開く 頂く 願う 仕舞う"
_EXACT_ONLY = {"かく", "きく", "かす", "さす", "なす", "つく", "でる", "ぐむ", "びる", "めく", "らぐ", "やぐ", "むく", "なく"}
_SUFFIXES = sorted(((ending, rule) for rule, words in ENDINGS.items() for ending in words.split()),
                   key=lambda item: (-len(item[0]), item[0], item[1]))


def inflection_rules(expression: str) -> str:
    if not is_japanese_form(expression):
        return ""
    # These bare kana spellings have both ichidan and godan lexical senses.
    if expression in {"いる", "きる", "かえる"}:
        return "v1 v5"
    for ending, rule in _SUFFIXES:
        if expression.endswith(ending) and (ending not in _EXACT_ONLY or expression == ending):
            return rule
    return ""
