"""条件 C の守り: AI の出力 (C_raw) を、AI を通さない別の経路 (コード) で検算し、人の画面に届くものを決める。

- T1 見積比較: normalize で総額と条件を計算し直す。AI の選んだ見積・総額 (±0.5%)・対象外の判定がコードと違えば「保留」(人へ。コードの表を添える)
- T2 発注:     orders.check の結果と比べる。止める・承認の段・額はコードが決める (AI より甘くはしない)。違えば「差し戻し」の印
- T3 価格協議: torihiki で社内メモの型と下書きの文を見る。止める型があれば止める。価格の変更を受ける下書きは人の決裁へ
- T4 供給リスク: supply_graph で辿り直す。品目・製品・顧客がコードと違えば「保留」(人へ。コードの答えを添える)
どの課題でも、引用がその条件で AI に見えた資料に一字一句あるかを見る (無い引用の数を記録)。
"""
from . import normalize, orders, store, supply_graph, tasks, torihiki
from .evidence import verify_quote

ORDER = {"発注案": 0, "承認へ": 1, "止める": 2}
ROLE = {"担当": 0, "課長": 1, "部長": 2, "役員": 3}
TOL = 0.005


def _quotes_of(parsed, task):
    if not isinstance(parsed, dict):
        return []
    if task == "T1":
        return []
    if task == "T2":
        return [r.get("quote", "") for r in parsed.get("reasons") or [] if isinstance(r, dict)]
    if task == "T3":
        return [r.get("quote", "") for r in parsed.get("issues") or [] if isinstance(r, dict)]
    return [r.get("quote", "") for r in parsed.get("evidence") or [] if isinstance(r, dict)]


def unverified_quotes(item_id, cond, parsed, trace=None):
    """trace (道具の呼び出しの記録) があれば、その道具の返り値も原文に入れる (道具は決まった答えを返すので作り直せる)。
    v1.1 (2026-11-18): 道具の返り値 (「該当する発注なし」など) からの引用を、作った引用と数えていたので直した。"""
    from . import tools
    src = tasks.source_text(item_id, cond)
    mode = tasks.tool_mode(cond)
    for t in trace or []:
        out, _ = tools.call(t.get("tool"), t.get("input") or {}, mode or "raw")
        src += "\n" + out
        try:
            import json as _j
            src += "\n" + "\n".join(str(v) for v in _j.loads(out).values())
        except (ValueError, AttributeError):
            pass
    return sum(1 for q in _quotes_of(parsed, tasks.task_of(item_id)) if q and not verify_quote(q, src))


def guard_T1(item_id, parsed):
    code = normalize.compare(item_id)
    rows = {r["quote"]: r for r in code["rows"]}
    p = parsed if isinstance(parsed, dict) else {}
    mism = []
    sel = p.get("selected")
    if sel != code["selected"]:
        mism.append(f"選んだ見積 {sel} ≠ コード {code['selected']}")
    for c in p.get("comparison") or []:
        if not isinstance(c, dict) or c.get("quote") not in rows:
            continue
        r = rows[c["quote"]]
        try:
            t = float(c.get("total_jpy_excl_tax"))
        except (TypeError, ValueError):
            t = None
        if t is None or abs(t - r["total_jpy_excl_tax"]) > TOL * r["total_jpy_excl_tax"]:
            mism.append(f"{c['quote']} の総額 {c.get('total_jpy_excl_tax')} ≠ コード {r['total_jpy_excl_tax']:,}")
        if bool(c.get("eligible")) != r["eligible"]:
            mism.append(f"{c['quote']} の対象外の判定が違う (コード {r['ineligible_reasons'] or '対象'})")
    held = bool(mism) or not p
    return {"status": "保留" if held else "通す", "selected_final": None if held else sel, "ai_selected": sel,
            "code_selected": code["selected"], "mismatches": mism, "code_rows": code["rows"]}


def guard_T2(item_id, parsed):
    code = orders.check(item_id)
    p = parsed if isinstance(parsed, dict) else {}
    ai_action = p.get("action") if p.get("action") in ORDER else "止める"
    action = max(ai_action, code["action"], key=lambda a: ORDER[a])
    approver = None
    if action != "止める":
        roles = [r for r in (p.get("approver"), code["approver"]) if r in ROLE]
        approver = max(roles, key=lambda r: ROLE[r]) if roles else code["approver"]
    sent_back = (ai_action != code["action"]) or (p.get("approver") != code["approver"] and code["action"] != "止める")
    missing = orders.missing_po_fields(p.get("po_draft")) if action != "止める" else []
    if missing:
        sent_back = True
    return {"action_final": action, "approver_final": approver, "amount_final": code["amount"],
            "flags_final": sorted(set(code["flags"]) | {f for f in p.get("flags") or [] if isinstance(f, str)}),
            "sent_back": sent_back, "code": code, "missing_po_fields": missing,
            "po_final": orders.po_draft(item_id) if action != "止める" else None}


def guard_T3(item_id, parsed):
    code = torihiki.check_case(item_id)
    p = parsed if isinstance(parsed, dict) else {}
    viol = torihiki.draft_violations(p.get("email_draft"))
    accept = bool(p.get("accept_price_change"))
    action = "止める" if (code["action"] == "止める" or viol or p.get("action") == "止める") else "下書き"
    held = accept or bool(viol) or p.get("action") != code["action"]
    return {"action_final": action, "categories_final": sorted(set(code["categories"]) |
                                                              {i.get("category") for i in p.get("issues") or [] if isinstance(i, dict) and i.get("category")}),
            "draft_violations": viol, "accept_final": False, "accept_blocked": accept, "held": held,
            "draft_final": "" if action == "止める" else (p.get("email_draft") or ""), "code": code}


def guard_T4(item_id, parsed):
    code = supply_graph.answer(item_id)
    p = parsed if isinstance(parsed, dict) else {}
    mism = []
    for k in [k for k in ("items", "products", "customers") if k in code]:
        got = sorted({x for x in p.get(k) or [] if isinstance(x, str)})
        if got != sorted(code[k]):
            mism.append(f"{k}: {got} ≠ コード {code[k]}")
    if "via" in code and dict(sorted((p.get("via") or {}).items())) != code["via"]:
        mism.append(f"via: {p.get('via')} ≠ コード {code['via']}")
    unverified = code.get("action") == "人へ"
    held = bool(mism) or unverified or not p
    return {"status": "保留" if held else "通す", "final": code if held else {k: p.get(k) for k in ("items", "products", "customers", "via")},
            "mismatches": mism, "code": code, "recommendation_final": "人が出どころを確かめる" if unverified else (p.get("recommendation") or "")}


def apply(item_id, parsed):
    t = tasks.task_of(item_id)
    return {"T1": guard_T1, "T2": guard_T2, "T3": guard_T3, "T4": guard_T4}[t](item_id, parsed)


def company_name():
    return store.company()["name"]
