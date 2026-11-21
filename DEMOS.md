# 実演の一覧 (どれも数秒。キー不要)

| # | コマンド | 見せるもの | 部 |
|---|---|---|---|
| l01 | `python -X utf8 -m procai tour` | 会社とデータ・取引先の規模・品目の区分 (製造の委託か市販品か) | P4 |
| l02 | `python -X utf8 -m procai compare --naive` | 12 件の見積比較: コードの総額と「書いてある単価」の最安 (10 件で取り違える) | P2・P6 |
| l03 | `python -X utf8 -m procai compare R-01 R-02 R-12` | 税込と税抜・箱と袋と個・kg と枚 | P6 |
| l04 | `python -X utf8 -m procai compare R-03 R-05 R-08 R-10` | 外貨と送料・最低発注数量・段階の単価・金型費 | P6 |
| l05 | `python -X utf8 -m procai compare R-06 R-07` | 有効期限切れ・納期が間に合わない | P6 |
| l06 | `python -X utf8 -m procai ask R-12 --provider mock_naive --cond A` | 筋書きの AI の取り違えを、守りが保留にする | P6 |
| l07 | `python -X utf8 -m procai order` | 発注の関門 10 件 (上限・分割・二重・未登録・見積・60 日・手形・口頭の承認) | P8 |
| l08 | `python -X utf8 -m procai negotiate` | 価格協議: 社内メモの型の検出 (一方的な決定・みなし合意・減額・振込手数料・手形) | P9 |
| l09 | `python -X utf8 -m procai risk` | 単一調達・隠れた単一調達・ニュースの影響を関係図で辿る | P10 |
| l10 | `python -X utf8 -m procai risk --news NW-02` | 名前が同じでも所在地が違う会社 | P10 |
| l11 | `python -X utf8 -m procai attacks` | 見積・手紙・ニュースの隠し指示・偽の仕入先・口頭の承認 | P11 |
| l12 | `python -X utf8 -m procai ledger` | 協議の記録と承認の列 | P9・P13 |
| l13 | `python -X utf8 -m procai usecase` | 相見積 → 発注 → 値上げの申し入れ → 単一調達の確かめ の通し | P13 |
| l14 | `python -X utf8 -m procai ask REQ-03 --provider replay --cond B` | 本物の記録 (実行後) と守りを通した後 | P12 |
| 実測 | `python -X utf8 -m experiment.show smoke` / `python -X utf8 -m experiment.harness score` | 筋書きの対戦表 / 本物の記録の採点し直し | P12 |
| 検査 | `python -X utf8 tools/selfcheck.py` | 自己検査 | P15 |
