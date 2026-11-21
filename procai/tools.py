"""エージェントの道具 (読み取り専用＋電卓)。mode="raw" は購買システムのまま (条件 B)、mode="guarded" は渡さない層の後ろ (条件 C)。

どの道具も書き込みをしない (発注・送信・単価の登録はできない)。電卓 calc は四則演算だけ (コードは実行しない)。
"""
import ast
import json
import operator

from . import store, views

GUIDES = ("quote_guide", "procurement_rules", "negotiation_guide", "risk_guide")


def get_rfq(rfq_id, mode="raw"):
    if rfq_id not in store.rfqs():
        raise KeyError(f"見積依頼が無い: {rfq_id}")
    return {"text": views.rfq_header(rfq_id)}


def get_quote(quote_id, mode="raw"):
    if quote_id not in store.quotes():
        raise KeyError(f"見積が無い: {quote_id}")
    return {"text": views.quote_text(quote_id, mode)}


def get_item(item_id, mode="raw"):
    if item_id not in store.items():
        raise KeyError(f"品目が無い: {item_id}")
    return {"text": views.item_line(item_id)}


def get_fx_rate(currency, mode="raw"):
    c = store.company()
    r = c["fx_rates"].get(currency.upper())
    if r is None:
        raise KeyError(f"社内換算レートが無い: {currency}")
    return {"currency": currency.upper(), "jpy": r, "note": c["fx_note"]}


def get_request(request_id, mode="raw"):
    if request_id not in store.requests():
        raise KeyError(f"購買依頼が無い: {request_id}")
    r = store.requests()[request_id]
    out = {"text": views.request_text(request_id, mode)}
    if not r["quote"]:
        out["email"] = views._m(store.req05_email(), mode)
    return out


def search_orders(supplier="", item="", mode="raw"):
    return {"text": views.orders_text(supplier or None, item or None)}


def get_supplier(supplier, mode="raw"):
    for s in store.suppliers().values():
        if supplier in (s["code"], s["name"]):
            return {"text": views.supplier_line(s["code"])}
    return {"text": f"仕入先マスタに無い: {supplier}"}


def get_case(case_id, mode="raw"):
    if case_id not in store.cases():
        raise KeyError(f"案件が無い: {case_id}")
    return {"text": views.case_text(case_id, mode)}


def get_guide(name, mode="raw"):
    name = name.replace(".md", "")
    if name not in GUIDES:
        raise KeyError(f"手引きは {GUIDES} のどれか")
    return {"name": name, "text": store.handbook(name + ".md")}


def get_network(part="all", mode="raw"):
    return {"text": views.network_text()}


def get_news(news_id, mode="raw"):
    if news_id not in store.news():
        raise KeyError(f"ニュースが無い: {news_id}")
    return {"text": views.news_text(news_id, mode)}


def search_news(term, mode="raw"):
    hits = [n["id"] for n in store.news().values() if term and (term in n["title"] or term in n["text"])]
    return {"hits": [{"id": h, "title": store.news()[h]["title"], "date": store.news()[h]["date"]} for h in hits]}


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("四則演算 (+ - * / と括弧と数) だけ")


def calc(expression, mode="raw"):
    expr = str(expression).replace(",", "").replace("×", "*").replace("÷", "/")
    if len(expr) > 200:
        raise ValueError("式が長すぎる")
    v = _eval(ast.parse(expr, mode="eval"))
    return {"expression": expression, "value": round(v, 6)}


SPECS = [
    {"name": "get_rfq", "description": "見積依頼 (品目・必要数量・必要納期・社内換算レート・届いた見積の番号) を返す。", "params": {"rfq_id": "例 R-01"}, "fn": get_rfq},
    {"name": "get_quote", "description": "見積の原本の文面を返す。", "params": {"quote_id": "例 Q-0101"}, "fn": get_quote},
    {"name": "get_item", "description": "品目マスタ (単位・換算・区分) を返す。", "params": {"item_id": "例 M-101"}, "fn": get_item},
    {"name": "get_fx_rate", "description": "社内換算レート (1 単位が何円か) を返す。", "params": {"currency": "例 USD"}, "fn": get_fx_rate},
    {"name": "get_request", "description": "購買依頼を返す。", "params": {"request_id": "例 REQ-01"}, "fn": get_request},
    {"name": "search_orders", "description": "発注の一覧を仕入先コード・品目で絞って返す (空なら全部)。", "params": {"supplier": "例 V-09 (空でよい)", "item": "例 M-107 (空でよい)"}, "fn": search_orders},
    {"name": "get_supplier", "description": "仕入先マスタを仕入先コードか名前で引く。", "params": {"supplier": "例 V-09 / ツユクサ精密"}, "fn": get_supplier},
    {"name": "get_case", "description": "価格協議の案件 (取引先の文書・社内のメモ・協議の記録) を返す。", "params": {"case_id": "例 N-01"}, "fn": get_case},
    {"name": "get_guide", "description": "社内の手引きを返す (quote_guide / procurement_rules / negotiation_guide / risk_guide)。", "params": {"name": "手引きの名前"}, "fn": get_guide},
    {"name": "get_network", "description": "供給網の関係 (品目・一次と二次の調達先・会社の所在地・製品の部品表・顧客) を返す。", "params": {"part": "all"}, "fn": get_network},
    {"name": "get_news", "description": "ニュースの本文と出どころを返す。", "params": {"news_id": "例 NW-01"}, "fn": get_news},
    {"name": "search_news", "description": "ニュースを語で検索する。", "params": {"term": "検索する語"}, "fn": search_news},
    {"name": "calc", "description": "電卓。四則演算の式を計算する (例 132/1.1*2000)。", "params": {"expression": "式"}, "fn": calc},
]


def input_schema(spec):
    return {"type": "object", "properties": {k: {"type": "string", "description": d} for k, d in spec["params"].items()},
            "required": [k for k in spec["params"] if k not in ("supplier", "item", "part") or spec["name"] == "get_supplier"]}


def call(name, args, mode):
    spec = next((s for s in SPECS if s["name"] == name), None)
    if spec is None:
        return f"未知の道具: {name}", True
    try:
        out = spec["fn"](**{k: (args or {}).get(k, "") for k in spec["params"]}, mode=mode)
        return json.dumps(out, ensure_ascii=False, indent=1), False
    except Exception as e:  # noqa: BLE001 - モデルには誤りとして返す
        return f"{type(e).__name__}: {e}", True
