## ----------------------------------
## 基本情報、ライセンス
## ----------------------------------

タイトル: 『日本語文型データベース』
編者: プラシャント・パルデシ、砂川 有里子
出版者: 国立国語研究所 研究系
出版地: 東京
出版年月日: 2026年1月26日
doi: https://doi.org/10.15084/0002000610
ライセンス: CC BY 4.0（https://creativecommons.org/licenses/by/4.0/）
連絡先: プラシャント・パルデシ (prashant@ninjal.ac.jp)
バージョン: 2026.01.26版
ファンド: ①国立国語研究所共同研究プロジェクト（2008年度）独創・発展型共同研究プロジェクト「日本語学習者用基本動詞用法ハンドブックの作成」、 ②国立国語研究所共同研究プロジェクト(2009～2015年度)「述語構造の意味範疇の普遍性と多様性」、③国立国語研究所共同研究プロジェクト (2016～2021年度)「日本語学習者のコミュニケーションの多角的解明」傘下のサブプロジェクト「日本語学習のためのリソース開発」「日本語基本動詞ハンドブック」、④科学研究費補助金研究課題16K13228「挑戦的萌芽研究「大規模コーパスに基づく日本語新機能語の基礎研究と機能語検索ツールへの応用」（代表：Prashant Pardeshi＠国立国語研究所）」、⑤科学研究費補助金研究課題15H03210「統語・意味解析情報タグ付きコーパス開発用アノテーション研究：複文を中心に」（代表：Prashant Pardeshi＠国立国語研究所）」、⑥科学研究費補助金研究課題18H03575「基盤研究（A）「準均衡超大規模日本語コーパスと高速検索ツールの開発」（代表：今井新悟＠早稲田大学）」、⑦科学研究費補助金研究課題23K21944「学習者のニーズを反映した大規模な動詞用法データベースとオンライン教材の開発と公開（代表：Prashant Pardeshi＠国立国語研究所）」

@misc{pardeshi26a,
	address = {東京},
	author = {パルデシ, プラシャント and 砂川 有里子},
	publisher = {国立国語研究所 研究系},
	title = {日本語文型データベース},
	year = {2026},
	yomi = {Pardeshi, Prashant and Sunakawa Yuriko},
	doi = {10.15084/0002000610}
}

@misc{pardeshi26a,
	address = {Tokyo},
	author = {Pardeshi, Prashant and Sunakawa Yuriko},
	publisher = {NINJAL Research Department},
	title = {Nihongo Bunkei Database},
	year = {2026},
	doi = {10.15084/0002000610}
}

## ----------------------------------
## メンバー
## ----------------------------------

監修担当
福島 佐知 Fukushima Sachi／友松 悦子 Tomomatsu Etsuko

執筆担当
福島 佐知 Fukushima Sachi／友松 悦子 Tomomatsu Etsuko／盤若 洋子 Hannya Yoko／伊藤 江美 Ito Emi／西島 道 Nishijima Michi／宮島 敦子 Miyajima Atsuko／中村かおり Nakamura Kaori／黒羽千佳子 Kuroha Chikako／町田亙 Machida Wataru／寺田 友子 Terada Tomoko／梶原 彩子 Kajiwara Ayako／松浦 光 Matsuura Hikaru／堀内 仁 HORIUCHI Hitoshi

校閲担当
クロス 尚美 Cross Naomi／渡部 真由美 Watanabe Mayumi／田中 祥 Tanaka Sachi／中溝 朋子 Nakamizo Tomoko／高原 真理 Takahara Mari／生天目 知美 Nabatame Tomomi／田川 拓海 Tagawa Takumi

コーディネーション・連絡・調整担当
アルン・シャム SHAYM Arun

## ----------------------------------
## ファイルの説明
## ----------------------------------

「日本語文型データベース」は、日本語教育に必要な文型を難易度で分類し、それぞれの文型に接続情報や用例を付与したデータベースです。見出しの一覧はheadwords.txtをご参照ください。見出し語数は８００語です。

## ----------------------------------
## ファイルの構造
## ----------------------------------

XMLファイルの構造は以下のようになっています。

・ふりがなは「〓間〔あいだ〕」のような形式で表現しています。
・改行は「&#10;」で表しています。
・xmlファイルは見出し語単位で出力しています。

<?xml version="1.0" encoding="UTF-8"?>
<Entry>
  <SentencePattern>～〓間〔あいだ〕</SentencePattern>
  <Reading>～あいだ</Reading>
  <GeneralExplanation></GeneralExplanation>
  <Sense>
    <SenceCategory>〓時〔とき〕｜〓期間〔きかん〕</SenceCategory>
    <Level>4</Level>
    <Usage>～の〓期間〔きかん〕〓中〔ちゅう〕ずっと、ある〓状態〔じょうたい〕や〓動作〔どうさ〕・〓出来事〔できごと〕が〓続〔つづ〕くと〓言〔い〕いたいときに〓使〔つか〕います。&#10;「〜〓間〔あいだ〕のN」の〓形〔かたち〕でも〓使〔つか〕います。</Usage>
    <UsageNotes>「〜」には、〓継続〔けいぞく〕〓的〔てき〕な〓動作〔どうさ〕・〓状態〔じょうたい〕を〓表〔あらわ〕す〓文〔ぶん〕や〓期間〔きかん〕を〓表〔あらわ〕す〓言葉〔ことば〕がきます。「〜〓間〔あいだ〕」の〓後〔あと〕には、〓継続〔けいぞく〕〓的〔てき〕な〓動作〔どうさ〕・〓状態〔じょうたい〕を〓表〔あらわ〕す〓文〔ぶん〕がきます。</UsageNotes>
    <Style></Style>
    <CommonlyUsedWordsTogether>ずっと</CommonlyUsedWordsTogether>
    <Orthography>〜〓間〔あいだ〕・〜あいだ</Orthography>
    <AlternativeForm></AlternativeForm>
    <SimilarExpressions></SimilarExpressions>
    <ContrastingExpression></ContrastingExpression>
    <Connection>
      <ConnectionType>Vる〓間〔あいだ〕・Vている〓間〔あいだ〕／Vない〓間〔あいだ〕</ConnectionType>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>シュミットさんは〓日本〔にほん〕にいる｛〓間〔あいだ〕｝、ずっと〓英語〔えいご〕を〓教〔おし〕えていました。</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>このフリーの〓仕事〔しごと〕がある｛〓間〔あいだ〕｝は、〓私〔わたし〕は〓何〔なん〕とか〓食〔た〕べていけるだろう。</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>〓雨天〔うてん〕の〓日〔ひ〕が〓続〔つづ〕いている｛〓間〔あいだ〕｝、〓車〔くるま〕いす〓生活〔せいかつ〕の〓私〔わたし〕は〓結局〔けっきょく〕どこへも〓行〔い〕けなかった。</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>〓子〔こ〕どもたちがテレビを〓見〔み〕ている｛〓間〔あいだ〕｝、〓私〔わたし〕は〓旅行〔りょこう〕〓先〔さき〕のホテルを〓調〔しら〕べていた。</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>〓赤〔あか〕ちゃんが〓寝〔ね〕ている｛〓間〔あいだ〕｝の、ほっとした〓時間〔じかん〕が〓私〔わたし〕は〓好〔す〕きだ。</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>〓上司〔じょうし〕が〓出張〔しゅっちょう〕でいない｛〓間〔あいだ〕｝、〓私〔わたし〕がプロジェクトのリーダーを〓務〔つと〕めた。</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
    </Connection>
    <Connection>
      <ConnectionType>Nの〓間〔あいだ〕</ConnectionType>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>〓夏休〔なつやす〕みの｛〓間〔あいだ〕｝、ずっと〓海外〔かいがい〕にいました。</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>〓留守〔るす〕の｛〓間〔あいだ〕｝〓締〔し〕め〓切〔き〕っていたので、〓部屋〔へや〕の〓中〔なか〕に〓湿気〔しっけ〕がこもってしまった。</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>この〓3連休〔さんれんきゅう〕の｛〓間〔あいだ〕｝、ずっとインスタントラーメンばかり〓食〔た〕べていた。</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>〓由美〔ゆみ〕はパーティーの｛〓間〔あいだ〕｝、なぜか〓不機嫌〔ふきげん〕だった。</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>パスポートは〓旅行〔りょこう〕の｛〓間〔あいだ〕｝、〓常時〔じょうじ〕〓持〔も〕っていてください。</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
      <ExampleSet>
        <SceneDescription></SceneDescription>
        <Example>「〓留守〔るす〕の｛〓間〔あいだ〕｝のペットの〓世話〔せわ〕は〓誰〔だれ〕がしたの？」「ペットホテルに〓預〔あず〕けたよ」</Example>
        <ExampleNote></ExampleNote>
      </ExampleSet>
    </Connection>
  </Sense>
</Entry>