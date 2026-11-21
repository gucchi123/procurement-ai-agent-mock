"""要約を短い表で見せる。python -m experiment.show [smoke|real] [--results results]"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {"T1": "見積比較", "T2": "発注の判断", "T3": "価格協議", "T4": "供給リスク"}


def _r(x):
    if isinstance(x, dict) and "rate" in x:
        if not x["n"]:
            return "-"
        up = f" (0件・上限 {x['upper_if_zero']})" if x.get("upper_if_zero") else ""
        return f"{x['k']}/{x['n']}={x['rate']} {x['ci95']}{up}"
    return str(x)


def show(summary):
    for c, t in summary.items():
        print(f"\n===== 条件 {c} =====")
        for task in ("T1", "T2", "T3", "T4"):
            if task in t:
                print(f"[{task} {NAMES[task]}] " + " | ".join(f"{k} {_r(v)}" for k, v in t[task].items()))
        extra = {k: t[k] for k in ("unverified_quotes", "parse_failed") if k in t}
        if extra:
            print("[引用と形] " + json.dumps(extra, ensure_ascii=False))
        print("[費用] " + json.dumps(t.get("cost"), ensure_ascii=False))


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    argv = argv if argv is not None else sys.argv[1:]
    kind = argv[0] if argv else "smoke"
    if kind == "smoke":
        from experiment import harness
        print("筋書き (mock) の対戦表。性能の証拠ではない。A=素朴な作りの筋書き / C=守りつきの筋書き")
        show(harness.run_smoke(write=False)["summary"])
    else:
        rd = os.path.join(HERE, argv[argv.index("--results") + 1]) if "--results" in argv else os.path.join(HERE, "results")
        with open(os.path.join(rd, "real_summary.json"), encoding="utf-8") as f:
            show(json.load(f)["summary"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
