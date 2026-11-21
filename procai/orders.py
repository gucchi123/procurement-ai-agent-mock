"""発注の関門 (コード)。購買依頼を、権限の上限・分割・二重・登録・見積との一致・支払の条件で確かめる。

決まりは社内の手引き (data/handbook/procurement_rules.md) と同じ数字。法令の名前は「論点」として出すだけ (法的な判定ではない)。
  上限 (1 件の税抜・送料込の額): 担当 50 万円未満 / 課長 300 万円未満 / 部長 1,000 万円未満 / 役員 それ以上
  分割: 同じ仕入先・同じ品目で、依頼の日から 30 日前までの発注と合わせた額で決裁者を決める (SPLIT)
  二重: 同じ仕入先・同じ品目・同じ数量の未納の発注がある (DUPLICATE) → 止める
  登録: 仕入先マスタに無い (UNREGISTERED) → 止める (登録の手続きへ。振込先はメールの記載を使わない)
  見積: 依頼の単価が根拠の見積と違う (PRICE_MISMATCH) → 止める
  支払: 期日は受領日 (納期) から起算して 60 日以内 = 受領日を 1 日目と数えて 60 日目まで (PAY_TERM_60)
        手形は使わない (PAYMENT_TEGATA)。前払いは登録の済んだ仕入先と役員の承認だけ (ここでは未登録で止まる)
  口頭の承認: 「口頭で了承済み」は承認の記録にならない (VERBAL_APPROVAL_CLAIM)。決裁は手続きで
"""
import calendar
import datetime as dt
import re

from . import normalize, store

LIMITS = [("担当", 500_000), ("課長", 3_000_000), ("部長", 10_000_000), ("役員", None)]
SPLIT_DAYS = 30
PAY_DAYS = 60
REQUIRED_PO_FIELDS = ("発注日", "仕入先", "品名", "数量", "単価", "金額", "納期", "納入場所", "支払期日", "支払方法")


def approver_for(amount):
    for role, lim in LIMITS:
        if lim is None or amount < lim:
            return role
    return "役員"


def _d(s):
    return dt.date.fromisoformat(s)


def _month_end(y, m):
    while m > 12:
        y, m = y + 1, m - 12
    return dt.date(y, m, calendar.monthrange(y, m)[1])


def pay_date(receipt, terms):
    """支払条件から支払の日を出す。手形・前払いは None (別に扱う)。"""
    r = _d(receipt)
    if "手形" in terms or "前払い" in terms:
        return None
    if "翌々月末" in terms:
        return _month_end(r.year, r.month + 2)
    if "翌月末" in terms:
        return _month_end(r.year, r.month + 1)
    m = re.search(r"(\d+)\s*日", terms)
    if m:
        return r + dt.timedelta(days=int(m.group(1)))
    return None


def pay_deadline(receipt):
    """受領日を 1 日目と数えて 60 日目。"""
    return _d(receipt) + dt.timedelta(days=PAY_DAYS - 1)


def amount_of(req):
    return int(round(req["qty"] * req["unit_price"] + (req.get("shipping") or 0)))


def related_orders(req):
    d0 = _d(req["date"]) - dt.timedelta(days=SPLIT_DAYS)
    return [po for po in store.purchase_orders()
            if po["supplier"] == req["supplier"] and po["item"] == req["item"] and _d(po["date"]) >= d0]


def check(req_id):
    req = store.requests()[req_id]
    flags, notes = [], []
    amount = amount_of(req)
    sup = store.suppliers().get(req["supplier"]) if req["supplier"] else None
    if not sup or not sup.get("registered"):
        flags.append("UNREGISTERED")
        notes.append(f"仕入先マスタに無い: {req['supplier_name']}")
    rel = related_orders(req) if sup else []
    dup = [po for po in rel if po["qty"] == req["qty"] and po["status"].startswith("未納")]
    if dup:
        flags.append("DUPLICATE")
        notes.append(f"同じ数量の未納の発注がある: {dup[0]['id']}")
    combined = amount + sum(po["amount"] for po in rel if po not in dup)
    if rel and not dup and approver_for(combined) != approver_for(amount):
        flags.append("SPLIT")
        notes.append(f"30 日以内の同じ品目の発注と合わせて {combined:,} 円 → {approver_for(combined)}")
    if req.get("quote"):
        q = store.quotes()[req["quote"]]
        row = normalize.quote_total(q)
        qp = row["unit_price"] / (1.1 if q["tax"] == "incl" else 1.0)
        if abs(qp - req["unit_price"]) > 1e-9 and not q.get("tiers"):
            flags.append("PRICE_MISMATCH")
            notes.append(f"見積 {q['id']} の単価 (税抜) {qp:g} 円と違う: 依頼 {req['unit_price']:g} 円")
        elif q.get("tiers"):
            tp = float(normalize.unit_price_for(q, req["qty"]))
            if abs(tp - req["unit_price"]) > 1e-9:
                flags.append("PRICE_MISMATCH")
                notes.append(f"見積 {q['id']} の段の単価 {tp:g} 円と違う")
    elif sup:
        flags.append("PRICE_MISMATCH")
        notes.append("根拠の見積が無い")
    terms = req["pay_terms"]
    if "手形" in terms:
        flags.append("PAYMENT_TEGATA")
        notes.append("手形は使わない (社内の決まり。取適法では手形の交付は支払の遅延の論点)")
    pdate = pay_date(req["delivery"], terms)
    if pdate and pdate > pay_deadline(req["delivery"]):
        flags.append("PAY_TERM_60")
        notes.append(f"支払の日 {pdate} が受領日から 60 日目 ({pay_deadline(req['delivery'])}) より後")
    if re.search(r"口頭.{0,8}(了承|承認)|承認の手続きは省", req.get("memo", "")):
        flags.append("VERBAL_APPROVAL_CLAIM")
        notes.append("口頭の了承は承認の記録にならない。決裁は手続きで")
    stop_flags = {"UNREGISTERED", "DUPLICATE", "PRICE_MISMATCH", "PAYMENT_TEGATA", "PAY_TERM_60"}
    basis = combined if "SPLIT" in flags else amount
    role = approver_for(basis)
    if stop_flags & set(flags):
        action = "止める"
    elif role == "担当":
        action = "発注案"
    else:
        action = "承認へ"
    return {"request": req_id, "action": action, "approver": None if action == "止める" else role,
            "amount": amount, "combined_amount": combined if "SPLIT" in flags else None,
            "flags": flags, "notes": notes, "pay_date": str(pdate) if pdate else None,
            "pay_deadline": str(pay_deadline(req["delivery"]))}


def po_draft(req_id):
    """発注書の下書き (コードの版)。明示する事項をそろえる。"""
    req = store.requests()[req_id]
    it = store.items()[req["item"]]
    pdate = pay_date(req["delivery"], req["pay_terms"])
    return {"発注日": req["date"], "仕入先": req["supplier_name"], "品名": it["name"], "数量": req["qty"],
            "単価": req["unit_price"], "金額": amount_of(req), "納期": req["delivery"], "納入場所": req["place"],
            "支払期日": str(pdate) if pdate else None, "支払方法": req["pay_terms"]}


def missing_po_fields(draft):
    if not isinstance(draft, dict):
        return list(REQUIRED_PO_FIELDS)
    return [k for k in REQUIRED_PO_FIELDS if draft.get(k) in (None, "", [])]
