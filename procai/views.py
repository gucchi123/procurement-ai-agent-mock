"""購買システムの画面を文字にしたもの (条件 A・A+ で貼るもの、道具の返り値)。

mode="raw" は記録のまま (条件 A・A+・B)。mode="guarded" は渡さない層の後ろ (条件 C): 取引先の文書・ニュースの指示らしき文を伏せる。
"""
import json

from . import injection, store


def _m(text, mode):
    return injection.mask(text)[0] if mode == "guarded" else text


def _yen(x):
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,}"


def item_line(i):
    it = store.items()[i]
    conv = f"・換算 {it['conv_text']}" if it["conv_text"] else ""
    return f"{it['id']} {it['name']} (単位 {it['unit']}{conv}・区分 {it['spec']})"


def rfq_header(rfq_id):
    r = store.rfqs()[rfq_id]
    c = store.company()
    rates = " / ".join(f"1{k} = {v}円" for k, v in c["fx_rates"].items())
    return (f"見積依頼 {r['id']} (今日 {c['today']})\n"
            f"品目: {item_line(r['item'])}\n"
            f"必要数量: {r['need']:,}{store.items()[r['item']]['unit']} / 必要納期: {r['by']}\n"
            f"社内換算レート: {rates} ({c['fx_note']})・消費税 {c['tax_rate']}\n"
            f"届いた見積: {', '.join(r['quotes'])}")


def quote_text(qid, mode="raw"):
    q = store.quotes()[qid]
    sup = store.suppliers()[q["supplier"]]
    return f"[見積 {qid}・{sup['name']} ({q['supplier']})・受付 {q['received']}]\n" + _m(q["text"], mode)


def supplier_line(code):
    s = store.suppliers().get(code)
    if not s:
        return f"{code}: 仕入先マスタに無い"
    return (f"{s['code']} {s['name']} ({s['kind']}・所在地 {s['region']}・資本金 {s['capital_man_yen']:,}万円・"
            f"従業員 {s['employees']}名・{'登録済み' if s['registered'] else '未登録'})")


def supplier_master_text():
    return "\n".join(supplier_line(c) for c in store.suppliers())


def request_text(req_id, mode="raw"):
    r = store.requests()[req_id]
    it = store.items()[r["item"]]
    sup = f"{r['supplier_name']} ({r['supplier']})" if r["supplier"] else f"{r['supplier_name']} (仕入先コードなし)"
    return (f"購買依頼 {r['id']} (依頼日 {r['date']}・依頼者 {r['requester']})\n"
            f"品目: {it['id']} {it['name']} / 仕入先: {sup}\n"
            f"数量: {r['qty']:,}{it['unit']} / 単価 (税抜): {_yen(r['unit_price'])}円 / 送料: {r['shipping']}円\n"
            f"根拠の見積: {r['quote'] or 'なし (メールの見積)'} / 納期: {r['delivery']} / 納入場所: {r['place']}\n"
            f"支払条件: {r['pay_terms']}\n"
            f"依頼者のメモ: {r['memo']}")


def po_line(po):
    it = store.items()[po["item"]]
    sup = store.suppliers()[po["supplier"]]
    return (f"{po['id']} 発注日 {po['date']} {sup['name']} ({po['supplier']}) {it['id']} {it['name']} "
            f"{po['qty']:,}{it['unit']} × {_yen(po['unit_price'])}円 = {po['amount']:,}円 納期 {po['delivery']} [{po['status']}]")


def orders_text(supplier=None, item=None):
    pos = [p for p in store.purchase_orders() if (not supplier or p["supplier"] == supplier) and (not item or p["item"] == item)]
    return "\n".join(po_line(p) for p in pos) or "該当する発注なし"


def request_bundle(req_id, mode="raw"):
    """条件 A・A+ で貼るもの: 依頼・根拠の見積 (またはメール)・直近の発注の一覧・仕入先マスタ。"""
    r = store.requests()[req_id]
    quote = quote_text(r["quote"], mode) if r["quote"] else _m(store.req05_email(), mode)
    return [("購買依頼", request_text(req_id, mode)), ("根拠の見積", quote),
            ("直近の発注の一覧 (購買システム)", orders_text()), ("仕入先マスタ", supplier_master_text())]


def case_text(case_id, mode="raw"):
    c = store.cases()[case_id]
    sup = "全取引先" if c["supplier"] == "ALL" else supplier_line(c["supplier"])
    led = [e for e in store.ledger() if c["supplier"] in (e["supplier"], "ALL")]
    led_txt = "\n".join(f"- {e['date']} {store.suppliers()[e['supplier']]['name']} {e['kind']}: {e['summary']} ({e['by']})" for e in led) or "- 記録なし"
    parts = [f"案件 {c['id']}: {c['title']}", f"相手: {sup}"]
    if c.get("letter"):
        parts.append("取引先からの文書:\n" + _m(c["letter"], mode))
    parts.append("社内のメモ:\n" + c["memo"])
    parts.append("価格協議の記録 (この相手):\n" + led_txt)
    return "\n".join(parts)


def network_text():
    lines = ["[品目]"] + [item_line(i) for i in store.items()]
    lines.append("[調達先 (品目 → 一次の調達先と割合 → その調達先が頼っている二次)]")
    for i, srcs in store.sources().items():
        segs = []
        for s in srcs:
            t2 = "・".join(store.any_company(t)["name"] + f"({t})" for t in s["tier2"]) or "なし"
            segs.append(f"{store.suppliers()[s['supplier']]['name']}({s['supplier']}) {int(s['share'] * 100)}% ← 二次: {t2}")
        lines.append(f"{i}: " + " / ".join(segs))
    lines.append("[会社 (一次)]")
    lines += [f"{s['code']} {s['name']} 所在地 {s['region']}" for s in store.suppliers().values()]
    lines.append("[会社 (二次)]")
    lines += [f"{s['code']} {s['name']} ({s['kind']}) 所在地 {s['region']}" for s in store.tier2().values()]
    lines.append("[製品 (部品表と顧客)]")
    lines += [f"{p['id']} {p['name']}: 部品 {', '.join(p['bom'])} / 顧客 {', '.join(p['customers'])}" for p in store.products().values()]
    lines.append("[顧客]")
    lines += [f"{c['id']} {c['kind']}" for c in store.customers().values()]
    return "\n".join(lines)


def news_text(news_id, mode="raw"):
    n = store.news()[news_id]
    return f"[ニュース {n['id']}・{n['date']}・出どころ {n['source']}]\n{n['title']}\n" + _m(n["text"], mode)


def question_text(qid):
    return store.questions()[qid]["question"]


def dumps(x):
    return json.dumps(x, ensure_ascii=False, indent=1)
