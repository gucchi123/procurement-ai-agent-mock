"""見積の正規化と総額の検算 (AI を通さない別の経路)。

比べる額 = 必要数量を買うのに支払う総額。税抜・円・送料と初期費用 (金型費など) を含む。
  1. 単位をそろえる   見積の単位 (箱・袋・kg) を品目の単位に直す。端数は見積の単位で切り上げて買う
  2. 最低発注数量     必要数量が最低発注数量より少なければ、最低発注数量を買う
  3. 段階の単価       買う数量に当たる段の単価を使う
  4. 税               税込の見積は 1.1 で割って税抜に (消費税 10%)
  5. 通貨             外貨は社内換算レートで円に
  6. 送料・初期費用   別途のものを足す
  7. 条件             有効期限が今日より前 → 対象外 (EXPIRED)、納期が必要納期より後 → 対象外 (LATE)
分数 (fractions) で計算し、最後に円未満を四捨五入する。
"""
import math
from fractions import Fraction

from . import store

TAX = Fraction(11, 10)


def _f(x):
    return Fraction(str(x))


def base_per_quote_unit(q, item):
    """見積の単位 1 つが、品目の単位でいくつ分か。"""
    if q["per"] == "kg":
        return Fraction(1) / _f(item["conv"]["kg"])
    return _f(q["per"])


def unit_price_for(q, qty_base):
    if q.get("tiers"):
        price = None
        for t in sorted(q["tiers"], key=lambda t: t["min"]):
            if qty_base >= t["min"]:
                price = t["price"]
        return _f(price)
    return _f(q["price"])


def quote_total(q, rfq=None, today=None):
    rfq = rfq or next(r for r in store.rfqs().values() if q["id"] in r["quotes"])
    item = store.items()[rfq["item"]]
    today = today or store.today()
    need = max(rfq["need"], q.get("moq") or 0)
    per = base_per_quote_unit(q, item)
    n_units = math.ceil(Fraction(need) / per)
    qty_base = n_units * per
    price = unit_price_for(q, qty_base)
    goods = price * n_units
    if q["tax"] == "incl":
        goods = goods / TAX
    rate = _f(store.company()["fx_rates"].get(q["currency"], 1)) if q["currency"] != "JPY" else Fraction(1)
    ship_rate = _f(store.company()["fx_rates"].get(q["shipping_currency"], 1)) if q["shipping_currency"] != "JPY" else Fraction(1)
    total = goods * rate + _f(q.get("shipping") or 0) * ship_rate + _f(q.get("tooling") or 0)
    reasons = []
    if q["valid_until"] < today:
        reasons.append("EXPIRED")
    if q["delivery"] > rfq["by"]:
        reasons.append("LATE")
    yen = int((total + Fraction(1, 2)) // 1)
    return {"quote": q["id"], "supplier": q["supplier"], "total_jpy_excl_tax": yen, "eligible": not reasons,
            "ineligible_reasons": reasons, "buy_units": n_units, "quote_unit": q["quote_unit"],
            "buy_qty_base": float(qty_base) if qty_base.denominator != 1 else int(qty_base),
            "unit_price": float(price), "currency": q["currency"], "tax": q["tax"]}


def compare(rfq_id, today=None):
    rfq = store.rfqs()[rfq_id]
    rows = [quote_total(store.quotes()[qid], rfq, today) for qid in rfq["quotes"]]
    ok = [r for r in rows if r["eligible"]]
    best = min(ok, key=lambda r: r["total_jpy_excl_tax"]) if ok else None
    return {"rfq": rfq_id, "item": rfq["item"], "need": rfq["need"], "by": rfq["by"], "rows": rows,
            "selected": best["quote"] if best else None}


def naive_headline(rfq_id):
    """見積に書いてある単価をそのまま並べたときの最安 (単位・税・送料・条件を見ない)。教材の対比用。"""
    rfq = store.rfqs()[rfq_id]
    qs = [store.quotes()[q] for q in rfq["quotes"]]
    return min(qs, key=lambda q: q["price"])["id"]
