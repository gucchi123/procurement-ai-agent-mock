"""実測のハーネス。

  python -m experiment.harness smoke                     # mock の筋書き (A=mock_naive / C=mock)。費用 0。性能の証拠ではない
  python -m experiment.harness real --provider agent-sdk --conds A A+ B C --reps 1 [--tasks T1 ...] [--items P-01 ...]
                                                         # 同梱の記録を作った経路 (プランのログイン)。記録済みは飛ばす (続きから)
  python -m experiment.harness real --provider anthropic ...   # 各自のキー (費用が出る。件数を確かめてから)
  python -m experiment.harness score [--results results]  # 記録を採点 -> results/real_summary.json (キー不要 = 再生)
  python -m experiment.harness plan                       # 回す件数の見積もり (回さない)

記録: experiment/results/<条件>/<問>/<回>.json  (条件 A+ はフォルダ名 Aplus)
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from procai import providers, tasks        # noqa: E402
from scoring import score                  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_CONSECUTIVE_ERRORS = 3


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def select_items(task_filter=None, item_filter=None):
    its = [i for t, i in tasks.items() if not task_filter or t in task_filter]
    if item_filter:
        its = [i for i in its if i in set(item_filter)]
    return its


def run_smoke(write=True):
    recs = []
    for item in select_items():
        recs.append({"cond": "A", "item": item, "rep": 1, "parsed": providers.mock_naive(item, "A")})
        recs.append({"cond": "C", "item": item, "rep": 1, "parsed": providers.mock(item, "C")})
    rows = score.rows_from_records(recs)
    out = {"kind": "smoke", "note": "mock の筋書き (A=mock_naive・C=mock)。性能の証拠ではない。会社・取引先はすべて架空。",
           "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "summary": score.summarize(rows)}
    if write:
        _write_json(os.path.join(HERE, "results_mock", "smoke_summary.json"), out)
    return out


def run_real(provider, conds, reps, items, model=None, effort=None, redo=False, done_file=None, results_dir=None, log=print):
    if provider == "agent-sdk":
        from procai import agent_sdk as backend
    elif provider == "anthropic":
        from procai import anthropic_api as backend
    else:
        raise SystemExit("本物の実行は --provider agent-sdk (プランのログイン) か anthropic (各自のキー) を明示したときだけ")
    model = model or backend.DEFAULT_MODEL
    effort = effort or backend.DEFAULT_EFFORT
    results_dir = results_dir or providers.RESULTS_DIR
    todo = [(c, i, r) for r in reps for c in conds for i in items]
    done = skipped = errors_in_row = 0
    failed = []
    for n, (c, item, r) in enumerate(todo, 1):
        path = providers.result_path(c, item, r, results_dir)
        if os.path.isfile(path) and not redo:
            skipped += 1
            continue
        user = tasks.build_user(item, c)
        log(f"[{n}/{len(todo)}] {c} {item} 回{r} ...")
        try:
            res = backend.call(user, mode=tasks.tool_mode(c), model=model, effort=effort)
        except Exception as e:  # noqa: BLE001 - 記録せずに次へ
            res = {"error": f"{type(e).__name__}: {e}", "text": ""}
        if res.get("error") and not res.get("text"):
            errors_in_row += 1
            failed.append({"cond": c, "item": item, "rep": r, "error": str(res["error"])[:300]})
            log(f"    失敗 (記録しない): {str(res['error'])[:200]}")
            if errors_in_row >= MAX_CONSECUTIVE_ERRORS:
                log(f"    {MAX_CONSECUTIVE_ERRORS} 回続けて失敗。止める (続きは同じコマンドで)")
                break
            continue
        errors_in_row = 0
        parsed = providers.parse_json(res.get("text"))
        rec = {"cond": c, "item": item, "task": tasks.task_of(item), "rep": r, "provider": provider, "model": model,
               "effort": effort, "prompt_sha": tasks.prompt_fingerprint(), "input_chars": len(user), "tool_mode": tasks.tool_mode(c),
               "call": res, "parsed": parsed, "recorded": time.strftime("%Y-%m-%dT%H:%M:%S")}
        _write_json(path, rec)
        done += 1
        log(f"    記録 ({res.get('seconds')}s・道具 {len(res.get('trace') or [])} 回・形 {'OK' if parsed is not None else '壊れ'})")
    missing = [(c, i, r) for (c, i, r) in todo if not os.path.isfile(providers.result_path(c, i, r, results_dir))]
    out = {"kind": "real", "provider": provider, "model": model, "effort": effort, "conds": list(conds), "reps": list(reps),
           "items": len(items), "recorded_now": done, "skipped_existing": skipped, "failed": failed, "missing": len(missing),
           "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not missing and done_file:
        _write_json(done_file, out)
    return out


def run_score(results_dir=None, write=True):
    results_dir = results_dir or providers.RESULTS_DIR
    recs = score.load_records(results_dir)
    rows = score.rows_from_records(recs)
    out = {"kind": "real_summary", "note": "会社・取引先はすべて架空。正解は作成者が自社の手引きに照らして決めたもの (法的な判定ではない)。"
                                           "C+守り は C の記録に守りを通したもの (追加の実行なし)。費用は表示額 (プランの枠)。",
           "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "records": len(recs), "summary": score.summarize(rows) if rows else {},
           "rows": [dict(r) for r in rows]}
    if write and rows:
        _write_json(os.path.join(results_dir, "real_summary.json"), out)
    return out


def plan(conds, reps, items):
    n = len(conds) * len(reps) * len(items)
    return {"calls": n, "by_task": {t: sum(1 for i in items if tasks.task_of(i) == t) * len(conds) * len(reps) for t in tasks.TASKS}}


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="python -m experiment.harness")
    ap.add_argument("cmd", choices=["smoke", "real", "score", "plan"])
    ap.add_argument("--provider", default=None)
    ap.add_argument("--conds", nargs="+", default=list(tasks.CONDS))
    ap.add_argument("--reps", nargs="+", type=int, default=[1])
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--items", nargs="*")
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default=None)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--done-file", default=None)
    ap.add_argument("--results", default=None, help="記録の置き場 (experiment/ からの相対、既定 results)")
    ap.add_argument("--require", nargs="*", default=[], help="このファイルが全部あるときだけ回す (予行が通ってから本番、の順を守る)")
    a = ap.parse_args(argv)
    rd = os.path.join(HERE, a.results) if a.results else None
    if a.cmd == "smoke":
        print(json.dumps(run_smoke()["summary"], ensure_ascii=False, indent=1))
        return 0
    items = select_items(a.tasks, a.items)
    if a.cmd == "plan":
        print(json.dumps(plan(a.conds, a.reps, items), ensure_ascii=False))
        return 0
    if a.cmd == "score":
        res = run_score(rd)
        print(json.dumps(res["summary"], ensure_ascii=False, indent=1))
        return 0
    lack = [p for p in a.require if not os.path.isfile(p)]
    if lack:
        print(json.dumps({"kind": "real", "skipped": "前の段が終わっていない", "missing_required": lack}, ensure_ascii=False))
        return 4
    res = run_real(a.provider, a.conds, a.reps, items, a.model, a.effort, a.redo, a.done_file, rd)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if not res["missing"] else 3


if __name__ == "__main__":
    sys.exit(main())
