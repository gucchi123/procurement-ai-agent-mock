# 調達AIエージェント実装 ― 配布キット (course_procurement_ai)

架空のポンプ部品メーカー「株式会社そらみね製作所」の購買システムを手元で動かし、AI に **見積の比較・発注の判断・価格協議の文書・供給リスクの読み取り** をさせ、
**検算してから** 任せるための作り (見積の正規化と総額の検算・発注の上限と承認・協議の記録と止める型・関係図を辿る) を確かめるキットです。

- Python 3.10 以上の標準ライブラリだけで動きます。外部への送信はしません。API キーなしで全部の結果を再生できます。
- 🔴 会社・取引先・顧客はすべて架空です。実在の会社とは関係ありません。本キットは法的助言ではありません。最終判断は人が行います。

## はじめる

```
python -X utf8 tools/selfcheck.py            # 自己検査 (数秒)
python -X utf8 -m procai tour                # 会社とデータ
python -X utf8 -m procai compare --naive     # 見積の総額 (コード) と「書いてある単価」の最安を並べる
python -X utf8 -m experiment.show smoke      # 筋書き (mock) の対戦表。性能の証拠ではない
```

実演の一覧は `DEMOS.md`、決まりは `CONVENTIONS.md`。

## 中身

| 場所 | 中身 |
|---|---|
| `data/` | 購買システム (取引先 16・二次の仕入先 5・品目 12・製品 4・見積依頼 12 と見積 36・発注 5・購買依頼 10・価格協議の案件 8 と記録・ニュース 7・問い 8) と社内の手引き 4 本 |
| `procai/` | 部品: `normalize` (見積の正規化と総額)・`orders` (上限・分割・二重・登録・見積・支払)・`torihiki` (取適法の論点の目印)・`supply_graph` (関係図)・`injection`・`evidence`・`guards`・`tools`・`tasks`・`providers` |
| `experiment/` | 実測: 問題文 (`prompts/`)・仮説 (`hypotheses.md`、実行前に書いた)・ハーネス・本物の記録 (`results/`) |
| `scoring/` | 採点のコードと正解表 (`gold/`。手で計算した数字) |
| `tests/` | テスト (`python -m pytest` か `python -X utf8 tests/run_tests.py`) |

## 実測 (素の AI / 文脈つき / エージェント / 守りつき)

```
python -X utf8 -m experiment.harness plan                        # 回す件数 (152 回 / 1 周)
python -X utf8 -m experiment.harness score                       # 同梱の本物の記録を採点し直す (キー不要)
python -X utf8 -m experiment.show real                           # 対戦表
# 各自のキーで回す (費用が出ます。件数を確かめてから):
#   環境変数 ANTHROPIC_API_KEY を置いて
python -X utf8 -m experiment.harness real --provider anthropic --conds A C --items R-01 REQ-03
```

条件: A 素の AI (貼るだけ) / A+ 社内の手引きを足す / B 読み取り専用の道具と電卓を持つエージェント / C 同じ道具を渡さない層の後ろに置き、出力をコードの検算に通す。

## ライセンス

MIT License (`LICENSE`)。
