"""供給網の関係図 (品目 → 一次の調達先 → 二次の仕入先、品目 → 製品 → 顧客) をコードで辿る。

- 単一調達: 一次の調達先が 1 社だけの品目
- 隠れた単一調達: 一次は複数なのに、全部の調達先が同じ 1 社に頼っている品目 (各調達先の {自分} ∪ {二次} の共通部分)
- ニュースの影響: ニュースの会社を、名前 (ひらがなとカタカナの揺れは吸収) と所在地の両方で照合する。名前だけで決めない
  出どころ未確認のニュースは影響の判定に使わない (人に回して確かめる)
- 地域のニュース (大雪など): その地域にある一次・二次の会社を通る品目
"""
from . import store
from .evidence import kata, norm

UNVERIFIED_MARK = "未確認"


def _reach(src):
    return {src["supplier"], *src.get("tier2", [])}


def single_source():
    return sorted(i for i, srcs in store.sources().items() if len(srcs) == 1)


def hidden_concentration():
    out = {}
    for i, srcs in store.sources().items():
        if len(srcs) < 2:
            continue
        common = set.intersection(*[_reach(s) for s in srcs])
        if common:
            out[i] = sorted(common)[0]
    return dict(sorted(out.items()))


def products_of(items):
    return sorted({p["id"] for p in store.products().values() if set(p["bom"]) & set(items)})


def customers_of(products):
    return sorted({c for p in products for c in store.products()[p]["customers"]})


def match_company(name, region):
    """ニュースの会社 → 当社の取引先・二次のコード。名前と所在地の両方が合うときだけ。"""
    key = norm(kata(name))
    for code, c in {**store.suppliers(), **store.tier2()}.items():
        if norm(kata(c["name"])) == key and c["region"] == region:
            return code
    return None


def same_name_other(name, region):
    key = norm(kata(name))
    return [code for code, c in {**store.suppliers(), **store.tier2()}.items()
            if norm(kata(c["name"])) == key and c["region"] != region]


def items_through(codes):
    codes = set(codes)
    return sorted(i for i, srcs in store.sources().items() if any(_reach(s) & codes for s in srcs))


def impact_of_news(news_id):
    n = store.news()[news_id]
    if UNVERIFIED_MARK in n["source"]:
        return {"news": news_id, "items": [], "products": [], "customers": [], "action": "人へ",
                "note": "出どころ未確認。影響の判定に使わない (人が確かめる)", "matched": [], "same_name_other": []}
    codes, other = [], []
    for c in n.get("companies", []):
        m = match_company(c["name"], c["region"])
        if m:
            codes.append(m)
        else:
            other += same_name_other(c["name"], c["region"])
    for r in n.get("regions", []):
        codes += [code for code, c in {**store.suppliers(), **store.tier2()}.items() if c["region"] == r]
    its = items_through(codes)
    prods = products_of(its)
    return {"news": news_id, "items": its, "products": prods, "customers": customers_of(prods), "action": "報告",
            "matched": sorted(set(codes)), "same_name_other": sorted(set(other)),
            "note": "名前が同じでも所在地が違う会社は当社の取引先ではない" if other else ""}


def answer(question_id):
    """問い S-xx に対するコードの答え (守りの検算と、正解表の作り直しの確認に使う)。"""
    q = store.questions()[question_id]
    if q["kind"] == "single_source":
        its = single_source()
        return {"items": its, "products": products_of(its)}
    if q["kind"] == "hidden_concentration":
        hc = hidden_concentration()
        return {"items": sorted(hc), "via": hc}
    r = impact_of_news(q["news"])
    if q["kind"] == "price_signal":
        return {"items": r["items"], "products": r["products"]}
    return {k: r[k] for k in ("items", "products", "customers", "action", "note", "same_name_other")}
