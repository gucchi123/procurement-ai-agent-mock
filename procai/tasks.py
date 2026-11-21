"""問題集の 4 課題と、条件ごとに「何を渡すか」。問題文 (experiment/prompts/) は全条件で同じ。

条件:
  A   素の AI      道具なし・一発。対象を貼るだけ (購買システムの画面のまま。取引先の文書の指示らしき文も含む)
  A+  文脈つき     A + 社内の手引き (見積比較の手引き・購買規程・価格協議の手引き・供給リスクの手引き)
  B   エージェント  読み取り専用の道具と電卓で購買システムを引く (mode=raw。守りなし)
  C   守りつき     B と同じ道具を渡さない層 (指示らしき文を伏せる) の後ろに置く (mode=guarded)。出力は guards.py の守りを通す
"""
import hashlib
import os

from . import paths, store, views

CONDS = ("A", "A+", "B", "C")
TOOL_MODE = {"B": "raw", "C": "guarded"}
TASKS = ("T1", "T2", "T3", "T4")
TASK_TITLE = {"T1": "見積比較", "T2": "発注の判断", "T3": "価格協議の文書", "T4": "供給リスク"}
GUIDE_OF = {"T1": ["quote_guide"], "T2": ["procurement_rules"], "T3": ["negotiation_guide"], "T4": ["risk_guide"]}
TOOL_HINT = {
    "T1": "get_rfq / get_quote / get_item / get_fx_rate / get_guide / calc",
    "T2": "get_request / get_quote / search_orders / get_supplier / get_item / get_guide / calc",
    "T3": "get_case / get_supplier / search_orders / get_guide",
    "T4": "get_network / get_news / search_news / get_supplier / get_guide",
}


def items(task=None):
    out = []
    if task in (None, "T1"):
        out += [("T1", r) for r in store.rfqs()]
    if task in (None, "T2"):
        out += [("T2", r) for r in store.requests()]
    if task in (None, "T3"):
        out += [("T3", c) for c in store.cases()]
    if task in (None, "T4"):
        out += [("T4", q) for q in store.questions()]
    return out


def task_of(item_id):
    if item_id.startswith("REQ-"):
        return "T2"
    return {"R": "T1", "N": "T3", "S": "T4"}[item_id[0]]


def _prompt(name):
    with open(os.path.join(paths.EXPERIMENT, "prompts", name), "r", encoding="utf-8") as f:
        return f.read().rstrip() + "\n"


def prompt(task):
    return _prompt("common.txt") + "\n" + _prompt(f"{task}.txt")


def prompt_fingerprint():
    h = hashlib.sha256()
    for n in ["common.txt"] + [f"{t}.txt" for t in TASKS]:
        h.update(_prompt(n).encode("utf-8"))
    return h.hexdigest()[:16]


def _block(title, body):
    return f"===== {title} =====\n{body.rstrip()}\n"


def target_block(task, item_id, mode="raw"):
    """A / A+ で貼る対象 (購買システムの画面のまま)。"""
    if task == "T1":
        r = store.rfqs()[item_id]
        return [_block(f"見積依頼 {item_id}", views.rfq_header(item_id))] + \
               [_block(f"見積 {q}", views.quote_text(q, mode)) for q in r["quotes"]]
    if task == "T2":
        return [_block(t, b) for t, b in views.request_bundle(item_id, mode)]
    if task == "T3":
        return [_block(f"価格協議の案件 {item_id}", views.case_text(item_id, mode))]
    if task == "T4":
        q = store.questions()[item_id]
        parts = [_block("供給網の資料 (購買システム)", views.network_text())]
        if q["news"]:
            parts.append(_block(f"ニュース {q['news']}", views.news_text(q["news"], mode)))
        parts.append(_block(f"問い {item_id}", q["question"]))
        return parts
    raise ValueError(task)


def context_for(task):
    return [_block(f"社内の手引き: {g}", store.handbook(g + ".md")) for g in GUIDE_OF[task]]


def build_user(item_id, cond):
    task = task_of(item_id)
    if cond not in CONDS:
        raise ValueError(f"未知の条件: {cond}")
    parts = [prompt(task), "--- 以下に対象 (条件ごとに渡すものが変わる。問題文はここまで共通)\n"]
    if cond in ("A", "A+"):
        parts += target_block(task, item_id)
        if cond == "A+":
            parts += context_for(task)
    else:
        parts.append(f"対象: {item_id}\n")
        if task == "T4":
            q = store.questions()[item_id]
            parts.append(_block(f"問い {item_id}", q["question"] + (f"\n(ニュース {q['news']})" if q["news"] else "")))
        parts.append(f"購買システムは読み取り専用の道具 ({TOOL_HINT[task]}) で引ける。社内の手引きも get_guide で読める。\n")
    return "\n".join(parts)


def tool_mode(cond):
    return TOOL_MODE.get(cond)


def all_item_ids():
    return [i for _, i in items()]


def source_text(item_id, cond):
    """引用の照合に使う原文 (その条件で AI が見えたもの)。"""
    mode = "guarded" if cond == "C" else "raw"
    task = task_of(item_id)
    body = "\n".join(target_block(task, item_id, mode))
    if task == "T2":
        body += "\n" + views.supplier_master_text()
    if cond in ("A+", "B", "C"):
        body += "\n" + "\n".join(context_for(task))
    return body
