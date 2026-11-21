"""取適法 (製造委託等に係る中小受託事業者に対する代金の支払の遅延等の防止に関する法律、2026-01-01 施行) の「論点の目印」。

🔴 法的な判定ではない。キットは自社の手引きに照らして「専門家・法務に確かめる論点」を出すだけ。
   条番号は e-Gov の原文で確かめたもの。運用基準の本文は未照合の所がある。

applies(): この取引が取適法の論点になりうるか (製造委託 × 規模の基準)
  - 品目が当社図面・当社仕様 (製造の委託) のとき。市販品の購入は製造委託ではない
  - 規模: 当社 (資本金 3 億円超・従業員 300 人超) に対して、相手が資本金 3 億円以下 または 従業員 300 人以下
    (両方の基準に当たるときは資本金の基準で見る、と運用基準。ここでは「どちらかで当たれば候補」と広めに出す)
scan(): 価格協議の依頼文・社内メモから、手引きで止める型を拾う (正規表現)。AI を通さない別の経路
"""
import re

from . import store

CAPITAL_LINE = 30000      # 万円 (= 3 億円)
EMPLOYEE_LINE = 300

ARTICLES = {
    "UNILATERAL_PRICE": "協議に応じない一方的な代金の決定 (5条2項4号)・買いたたき (5条1項5号) の論点",
    "DEEMED_CONSENT": "返事がなければ合意とみなす (協議の記録にならない。5条2項4号の論点)",
    "REDUCTION": "相手の責めに帰すべき理由のない減額 (5条1項3号)",
    "TRANSFER_FEE": "振込手数料を代金から差し引く (運用基準で減額に当たる。合意があっても)",
    "TEGATA": "手形の交付 (5条1項2号 支払の遅延の括弧書き)",
    "INJECTION": "文書の中の指示らしき文 (取引先の文書は指示ではなくデータ)",
}

PATTERNS = [
    ("UNILATERAL_PRICE", r"(一切|絶対に?)受けない|協議(の場)?(は|を)?設けない|協議(は|を)しない|一律\s*\d+\s*%\s*の?値下げ|一律.{0,6}値下げ"),
    ("DEEMED_CONSENT", r"返事が?(なけ|無け)れば.{0,10}(合意|同意|承諾)|合意したものとみなす|みなす"),
    ("REDUCTION", r"(発注済み|納品済み).{0,40}(引いて|値引き|減額)|請求書を出し直"),
    ("TRANSFER_FEE", r"振込手数料.{0,30}差し引"),
    ("TEGATA", r"手形"),
    ("INJECTION", r"【[^】]*(AI|ＡＩ)[^】]*】"),
]


def is_small(sup):
    if not sup:
        return False
    return sup["capital_man_yen"] <= CAPITAL_LINE or sup["employees"] <= EMPLOYEE_LINE


def buyer_is_large():
    c = store.company()
    return c["capital_man_yen"] > CAPITAL_LINE or c["employees"] > EMPLOYEE_LINE


def item_is_commissioned(item_id):
    return not store.items()[item_id]["spec"].startswith("市販")


def applies(supplier_code, item_id=None):
    sup = store.suppliers().get(supplier_code)
    if not sup or not buyer_is_large():
        return False
    if item_id is not None and not item_is_commissioned(item_id):
        return False
    return is_small(sup)


def _clause(text, m):
    """当たった所を含む一節 (句点・改行・読点で区切る) を引用に使う。"""
    seps = ("。", "\n", "、")
    a = max(text.rfind(ch, 0, m.start()) for ch in seps) + 1
    ends = [i for i in (text.find(ch, m.end()) for ch in seps) if i >= 0]
    return text[a:min(ends) if ends else len(text)].strip()


def scan(text):
    text = text or ""
    out = []
    for cat, rx in PATTERNS:
        m = re.search(rx, text)
        if m:
            q = m.group(0) if cat == "INJECTION" else _clause(text, m)
            out.append({"category": cat, "quote": q, "note": ARTICLES[cat]})
    return out


def case_text(case):
    return (case.get("letter") or "") + "\n" + (case.get("memo") or "")


def check_case(case_id):
    """案件をコードで見る: 止める型があれば 止める、指示らしき文だけなら 下書き (指示は無視)、無ければ 下書き。"""
    c = store.cases()[case_id]
    found = scan(case_text(c))
    stop = [f for f in found if f["category"] != "INJECTION"]
    led = [e for e in store.ledger() if e["supplier"] == c["supplier"]]
    return {"case": case_id, "action": "止める" if stop else "下書き", "categories": sorted({f["category"] for f in found}),
            "findings": found, "ledger": led,
            "torihiki_candidate": (c["supplier"] != "ALL" and is_small(store.suppliers().get(c["supplier"])))}


BANNED_IN_DRAFT = [
    ("UNILATERAL_PRICE", r"(一切|絶対に?)(お受け|受け)(でき|し)?ません|協議(の場)?は(設け|いたし)ません|一律\s*\d+\s*[%％]\s*(の)?(値下げ|引き下げ)"),
    ("DEEMED_CONSENT", r"(ご返事|ご回答|返事|回答)が?(なけ|無け|ない場合).{0,20}(合意|同意|承諾)|とみなし"),
    ("TRANSFER_FEE", r"振込手数料.{0,30}差し引"),
    ("TEGATA", r"手形(で|にて|に)"),
    ("REDUCTION", r"(2|２)\s*[%％]\s*(を)?引いた|請求書を(再発行|出し直)"),
]


# 当たった後ろが打ち消し (「…とみなしたりすることはありません」) なら、禁じた文ではなく「しない」という約束。
# v1.1 (2026-11-18): 本物の記録で N-06 の正当な下書き 2 件を誤って拾ったので足した。
NEGATED_AFTER = re.compile(r"^[^。\n]{0,20}?(ことは|ことも|ことなど)?(ありません|ございません|いたしません|しません|致しません)")


def draft_violations(draft):
    d = draft or ""
    out = []
    for cat, rx in BANNED_IN_DRAFT:
        if any(not NEGATED_AFTER.search(d[m.end():]) for m in re.finditer(rx, d)):
            out.append(cat)
    return out
