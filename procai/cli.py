"""ラボ (どれも数秒・キー不要)。python -X utf8 -m procai <命令>

  tour                         会社とデータの一覧・取引先の規模と取適法の論点の候補
  compare [R-01 ...] [--naive] 見積比較: コードの正規化と総額 (--naive で「書いてある単価」の最安と並べる)
  order REQ-03 [...]           発注の関門: 上限・分割・二重・登録・見積・支払の条件
  negotiate N-01 [...]         価格協議: 社内メモの型の検出と、下書きの文の検査
  risk [S-01 ...|--news NW-01] 供給リスク: 単一調達・隠れた単一調達・ニュースの影響を辿る
  ask <問> --provider mock|mock_naive|replay [--cond A|A+|B|C] [--rep 1]
                               AI の答え (筋書きか記録) と、守りを通した後を並べる
  attacks                      見積・手紙・ニュースの中の指示らしき文を見つけて伏せる
  ledger                       価格協議の記録と、発注の承認の列
  usecase                      定期品の相見積 → 発注 → 値上げの申し入れ → 供給の兆し の通し
🔴 mock / mock_naive は筋書き。性能の証拠ではない。
"""
import argparse
import json
import sys

from . import guards, injection, normalize, orders, providers, store, supply_graph, tasks, torihiki, views


def _p(*a):
    print(*a)


def cmd_tour(a):
    c = store.company()
    _p(f"{c['name']} — {c['business']}・資本金 {c['capital_man_yen']:,}万円・従業員 {c['employees']}名・今日 {c['today']}")
    _p(f"取引先 {len(store.suppliers())} 社・二次の仕入先 {len(store.tier2())} 社・品目 {len(store.items())}・製品 {len(store.products())}・顧客 {len(store.customers())}")
    _p(f"見積依頼 {len(store.rfqs())} (見積 {len(store.quotes())} 通)・購買依頼 {len(store.requests())}・価格協議の案件 {len(store.cases())}・ニュース {len(store.news())}・問い {len(store.questions())}")
    _p("\n取引先 (取適法の論点の候補 = 当社図面・当社仕様の品目を、資本金 3 億円以下か従業員 300 人以下の相手に委託するとき):")
    for s in store.suppliers().values():
        _p(f"  {views.supplier_line(s['code'])}  {'← 規模の基準に当たる' if torihiki.is_small(s) else '← 規模の基準に当たらない'}")
    _p("\n品目の区分 (市販品の購入は製造の委託ではない):")
    for i in store.items().values():
        _p(f"  {i['id']} {i['name']}: {i['spec']}")
    _p("\n問題集: " + ", ".join(f"{t} {tasks.TASK_TITLE[t]} {sum(1 for x, _ in tasks.items() if x == t)} 問" for t in tasks.TASKS))
    _p("社内の手引き: " + ", ".join(store.handbook_names()))
    return 0


def cmd_compare(a):
    ids = a.ids or list(store.rfqs())
    for rid in ids:
        c = normalize.compare(rid)
        it = store.items()[c["item"]]
        _p(f"\n{rid} {it['name']} 必要 {c['need']:,}{it['unit']} / 必要納期 {c['by']}")
        for r in c["rows"]:
            q = store.quotes()[r["quote"]]
            head = f"{q['currency']} {q['price']}/{q['quote_unit']} ({'税込' if q['tax'] == 'incl' else '税抜'})"
            mark = "★" if r["quote"] == c["selected"] else " "
            ng = f" 対象外 {','.join(r['ineligible_reasons'])}" if r["ineligible_reasons"] else ""
            _p(f"  {mark} {r['quote']} {store.suppliers()[q['supplier']]['name']:<8} 書いてある単価 {head:<22} → 買う量 {r['buy_units']:,}{r['quote_unit']} → 総額 {r['total_jpy_excl_tax']:>11,} 円{ng}")
        if a.naive:
            nh = normalize.naive_headline(rid)
            _p(f"    書いてある単価の最安: {nh}  {'(同じ)' if nh == c['selected'] else '(違う → 取り違え)'}")
    return 0


def cmd_order(a):
    for rid in a.ids or list(store.requests()):
        c = orders.check(rid)
        _p(f"\n{views.request_text(rid)}")
        _p(f"  → 判定 {c['action']}  決裁者 {c['approver'] or '-'}  額 {c['amount']:,} 円" +
           (f" (合算 {c['combined_amount']:,} 円)" if c["combined_amount"] else "") + f"  支払の日 {c['pay_date']} / 60 日目 {c['pay_deadline']}")
        for f, n in zip(c["flags"], c["notes"]):
            _p(f"    [{f}] {n}")
    return 0


def cmd_negotiate(a):
    for cid in a.ids or list(store.cases()):
        c = torihiki.check_case(cid)
        case = store.cases()[cid]
        _p(f"\n{cid} {case['title']}  → {c['action']}  (取適法の規模の候補: {'全取引先 (相手ごとに違う)' if case['supplier'] == 'ALL' else ('はい' if c['torihiki_candidate'] else 'いいえ')})")
        for f in c["findings"]:
            _p(f"    [{f['category']}] 「{f['quote']}」 … {f['note']}")
    return 0


def cmd_risk(a):
    if a.news:
        r = supply_graph.impact_of_news(a.news)
        _p(views.news_text(a.news))
        _p(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    for sid in a.ids or list(store.questions()):
        q = store.questions()[sid]
        _p(f"\n{sid} {q['question']}" + (f" (ニュース {q['news']})" if q["news"] else ""))
        _p("  コードの答え: " + json.dumps(supply_graph.answer(sid), ensure_ascii=False))
    return 0


def cmd_ask(a):
    item = a.ids[0]
    cond = a.cond
    if a.provider == "mock":
        parsed = providers.mock(item, cond)
    elif a.provider == "mock_naive":
        parsed = providers.mock_naive(item, cond)
    elif a.provider == "replay":
        rec = providers.replay(item, cond, a.rep)
        parsed = rec.get("parsed")
        _p(f"(記録 {rec.get('recorded')}・{rec.get('model')}・effort {rec.get('effort')}・{(rec.get('call') or {}).get('seconds')} 秒・道具 {len((rec.get('call') or {}).get('trace') or [])} 回)")
    else:
        raise SystemExit("ask は mock / mock_naive / replay だけ (本物の実行は experiment.harness)")
    if a.provider.startswith("mock"):
        _p("🔴 筋書き (mock) の答え。性能の証拠ではない")
    _p("AI の答え:\n" + json.dumps(parsed, ensure_ascii=False, indent=1))
    g = guards.apply(item, parsed)
    g = {k: v for k, v in g.items() if k not in ("code_rows", "code")}
    _p("守りを通した後 (人の画面に届くもの):\n" + json.dumps(g, ensure_ascii=False, indent=1))
    return 0


def cmd_attacks(a):
    texts = [(f"見積 {q['id']}", q["text"]) for q in store.quotes().values()]
    texts += [(f"案件 {c['id']} の文書", c.get("letter") or "") for c in store.cases().values()]
    texts += [(f"ニュース {n['id']}", n["text"]) for n in store.news().values()]
    texts += [(f"依頼 {r['id']} のメモ", r["memo"]) for r in store.requests().values()]
    for name, t in texts:
        hits = injection.find(t)
        if hits:
            _p(f"{name}: 指示らしき文 {len(hits)} 件 → 伏せる")
            for h in hits:
                _p(f"    「{h}」")
    _p("\n口頭の承認の主張 (指示らしき文ではないが、手続きは省かない):")
    for r in store.requests().values():
        c = orders.check(r["id"])
        if "VERBAL_APPROVAL_CLAIM" in c["flags"]:
            _p(f"  {r['id']}: 「{r['memo']}」 → {c['action']} ({c['approver']})")
    _p("\n未登録の仕入先 (偽の仕入先の型):")
    for r in store.requests().values():
        if "UNREGISTERED" in orders.check(r["id"])["flags"]:
            _p(f"  {r['id']}: {r['supplier_name']} → 止める (登録の手続きが先・メールの振込先は使わない)")
    return 0


def cmd_ledger(a):
    _p("価格協議の記録 (日付・相手・内容・担当):")
    for e in store.ledger():
        _p(f"  {e['date']} {store.suppliers()[e['supplier']]['name']} {e['kind']}: {e['summary']} ({e['by']})")
    _p("\n発注の承認の列 (コードの判定):")
    for rid in store.requests():
        c = orders.check(rid)
        if c["action"] == "承認へ":
            _p(f"  {rid} → {c['approver']} の承認待ち  {c['amount']:,} 円 {c['flags'] or ''}")
    _p("\n止めた依頼 (直して出し直す):")
    for rid in store.requests():
        c = orders.check(rid)
        if c["action"] == "止める":
            _p(f"  {rid} {c['flags']}")
    _p("\n記録の保存: 発注・協議の記録を残す (取適法の作成・保存の規則では 2 年)")
    return 0


def cmd_usecase(a):
    _p("通し: インペラ (M-112) の相見積 → 発注 → 樹脂ケースの値上げの申し入れ → インペラの単一調達の確かめ")
    cmd_compare(argparse.Namespace(ids=["R-09"], naive=True))
    cmd_order(argparse.Namespace(ids=["REQ-10"]))
    cmd_negotiate(argparse.Namespace(ids=["N-01"]))
    _p("\nインペラ M-112 は単一調達か: " + ("はい" if "M-112" in supply_graph.single_source() else "いいえ"))
    _p("  使う製品: " + ", ".join(supply_graph.products_of(["M-112"])) + " / 顧客: " + ", ".join(supply_graph.customers_of(supply_graph.products_of(["M-112"]))))
    return 0


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="python -m procai")
    ap.add_argument("cmd", choices=["tour", "compare", "order", "negotiate", "risk", "ask", "attacks", "ledger", "usecase"])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--naive", action="store_true")
    ap.add_argument("--news", default=None)
    ap.add_argument("--provider", default="mock")
    ap.add_argument("--cond", default="C", choices=list(tasks.CONDS))
    ap.add_argument("--rep", type=int, default=1)
    a = ap.parse_args(argv)
    return globals()["cmd_" + a.cmd](a)
