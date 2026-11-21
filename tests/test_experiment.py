"""実測の仕組みのテスト (本物の AI は呼ばない。SDK と urlopen は差し替える)。"""
import json
import os
import sys
import tempfile
import types

from experiment import harness
from procai import agent_sdk, anthropic_api, guards, providers, tasks
from scoring import score


def test_smoke_guarded_has_no_unsafe_pass():
    s = harness.run_smoke(write=False)["summary"]
    a, cg = s["A"], s["C+守り"]
    assert a["T1"]["selected_ok"]["k"] < 6 and cg["T1"]["selected_ok"]["k"] == 12
    assert a["T2"]["unsafe_pass"]["k"] >= 3 and cg["T2"]["unsafe_pass"]["k"] == 0
    assert a["T3"]["accept"]["k"] == 1 and cg["T3"]["accept"]["k"] == 0
    assert a["T4"]["same_name_error"]["k"] == 1 and cg["T4"]["same_name_error"]["k"] == 0
    assert a["T4"]["injection_followed"]["k"] == 1 and cg["T4"]["injection_followed"]["k"] == 0


def test_guards_stop_naive_outputs():
    for it in tasks.all_item_ids():
        p = providers.mock_naive(it, "A")
        g = guards.apply(it, p)
        t = tasks.task_of(it)
        if t == "T1":
            assert g["selected_final"] in (None, g["code_selected"])
        if t == "T2":
            assert g["action_final"] == "止める" or g["code"]["action"] != "止める"
            assert g["amount_final"] == g["code"]["amount"]
        if t == "T3":
            assert g["accept_final"] is False and not __import__("procai").torihiki.draft_violations(g["draft_final"])


def test_broken_output_counts_as_wrong():
    rows = score.rows_from_records([{"cond": "C", "item": it, "rep": 1, "parsed": None} for it in ("R-01", "REQ-04", "N-01", "S-03")])
    raw = [r for r in rows if r["cond"] == "C"]
    assert all(not r["parsed"] for r in raw)
    assert not raw[0]["selected_ok"] and raw[1]["unsafe_pass"] and raw[2]["unsafe_draft"] and not raw[3]["items_ok"]
    guarded = [r for r in rows if r["cond"] == "C+守り"]
    assert guarded[0]["held"] and not guarded[1]["unsafe_pass"] and not guarded[2]["unsafe_draft"] and guarded[3]["held"]
    s = score.summarize(rows)
    assert s["C"]["parse_failed"] == 4


def test_wilson_and_rule_of_three():
    assert score.wilson(0, 10)[0] == 0.0 and score.rule_of_three(10) == 0.3 and score.rule_of_three(2) == 1.0
    lo, hi = score.wilson(5, 10)
    assert lo < 0.5 < hi


def test_parse_json_variants():
    assert providers.parse_json('前置き\n```json\n{"a": 1}\n```') == {"a": 1}
    assert providers.parse_json('説明 {"a": 2} 以上') == {"a": 2}
    assert providers.parse_json("JSON なし") is None


def _fake_backend(calls):
    def call(user, mode=None, model=None, effort=None):
        calls.append((mode, len(user)))
        item = next(i for i in tasks.all_item_ids() if f"対象: {i}\n" in user or f"===== 見積依頼 {i} =====" in user
                    or f"===== 購買依頼 =====\n購買依頼 {i} " in user or f"案件 {i}:" in user or f"===== 問い {i} =====" in user)
        return {"provider": "fake", "text": "```json\n" + json.dumps(providers.mock(item, "C"), ensure_ascii=False) + "\n```",
                "trace": [], "seconds": 0.01, "error": None}
    return call


def test_harness_real_records_resume_and_score(monkeypatch=None):
    calls = []
    orig = agent_sdk.call
    agent_sdk.call = _fake_backend(calls)
    try:
        with tempfile.TemporaryDirectory() as d:
            done = os.path.join(d, "_done", "x.json")
            items = ["R-01", "REQ-03", "N-08", "S-05"]
            out = harness.run_real("agent-sdk", ["A", "C"], [1], items, done_file=done, results_dir=d, log=lambda *a: None)
            assert out["recorded_now"] == 8 and out["missing"] == 0 and os.path.isfile(done)
            out2 = harness.run_real("agent-sdk", ["A", "C"], [1], items, results_dir=d, log=lambda *a: None)
            assert out2["recorded_now"] == 0 and out2["skipped_existing"] == 8
            rec = providers.replay("N-08", "C", 1, d)
            assert rec["prompt_sha"] == tasks.prompt_fingerprint() and rec["parsed"]["accept_price_change"] is False
            sc = harness.run_score(d, write=False)
            assert sc["records"] == 8 and sc["summary"]["C+守り"]["T2"]["unsafe_pass"]["k"] == 0
    finally:
        agent_sdk.call = orig
    assert [m for m, _ in calls].count("guarded") == 4 and [m for m, _ in calls].count(None) == 4


def test_harness_refuses_without_explicit_provider():
    try:
        harness.run_real("mock", ["A"], [1], ["R-01"], log=lambda *a: None)
        assert False
    except SystemExit:
        pass


def test_harness_require_blocks():
    with tempfile.TemporaryDirectory() as d:
        rc = harness.main(["real", "--provider", "agent-sdk", "--conds", "A", "--items", "R-01", "--results", d,
                           "--require", os.path.join(d, "nope.json")])
        assert rc == 4


def test_agent_sdk_uses_login_and_no_builtin_tools():
    seen = {}

    class Opt:
        def __init__(self, **kw):
            seen.update(kw)

    class TextBlock:
        def __init__(self, t):
            self.text = t

    class AssistantMessage:
        def __init__(self):
            self.model, self.content = "m", [TextBlock('{"selected": null}')]

    class ResultMessage:
        usage, total_cost_usd, num_turns, is_error, result = {"input_tokens": 1}, 0.0, 1, False, ""

    async def query(prompt, options):
        yield AssistantMessage()
        yield ResultMessage()

    fake = types.SimpleNamespace(ClaudeAgentOptions=Opt, query=query, AssistantMessage=AssistantMessage, TextBlock=TextBlock,
                                 ResultMessage=ResultMessage, SdkMcpTool=lambda **kw: kw,
                                 create_sdk_mcp_server=lambda name, tools: {"name": name, "tools": tools})
    old_mod, old_key = sys.modules.get("claude_agent_sdk"), os.environ.get("ANTHROPIC_API_KEY")
    sys.modules["claude_agent_sdk"] = fake
    os.environ["ANTHROPIC_API_KEY"] = "dummy-not-a-key"
    try:
        r = agent_sdk.call("x", mode="guarded")
        assert "ANTHROPIC_API_KEY" not in os.environ
        assert seen["env"]["ANTHROPIC_API_KEY"] == "" and seen["tools"] == [] and seen["setting_sources"] == []
        assert len(seen["allowed_tools"]) == 13 and seen["strict_mcp_config"] is True
        assert r["text"] == '{"selected": null}'
        agent_sdk.call("x", mode=None)
        assert seen["allowed_tools"] == [] and seen["max_turns"] == 1
    finally:
        if old_mod is None:
            sys.modules.pop("claude_agent_sdk", None)
        else:
            sys.modules["claude_agent_sdk"] = old_mod
        if old_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = old_key


def test_anthropic_api_tool_loop_and_missing_key():
    replies = [{"content": [{"type": "tool_use", "id": "t1", "name": "calc", "input": {"expression": "1+1"}}], "stop_reason": "tool_use",
                "usage": {"input_tokens": 3, "output_tokens": 2}},
               {"content": [{"type": "text", "text": '{"ok": 1}'}], "stop_reason": "end_turn", "usage": {"input_tokens": 4, "output_tokens": 1}}]
    sent = []

    class R:
        def __init__(self, b):
            self.b = b

        def read(self):
            return json.dumps(self.b).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_open(req, timeout=None):
        sent.append(json.loads(req.data.decode()))
        return R(replies[len(sent) - 1])

    old_open, old_key = anthropic_api._urlopen, os.environ.get("ANTHROPIC_API_KEY")
    anthropic_api._urlopen = fake_open
    try:
        os.environ["ANTHROPIC_API_KEY"] = "dummy-not-a-key"
        r = anthropic_api.call("x", mode="raw")
        assert r["text"] == '{"ok": 1}' and r["turns"] == 2 and r["trace"][0]["tool"] == "calc"
        assert len(sent[0]["tools"]) == 13 and "dummy" not in json.dumps(r)
        os.environ.pop("ANTHROPIC_API_KEY")
        try:
            anthropic_api.call("x")
            assert False
        except RuntimeError as e:
            assert "replay" in str(e)
    finally:
        anthropic_api._urlopen = old_open
        if old_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = old_key


def test_cli_labs_run():
    import contextlib
    import io
    from procai import cli
    for argv in (["tour"], ["compare", "--naive"], ["order"], ["negotiate"], ["risk"], ["risk", "--news", "NW-07"],
                 ["ask", "S-07", "--provider", "mock_naive", "--cond", "A"], ["ask", "REQ-01", "--provider", "mock"],
                 ["attacks"], ["ledger"], ["usecase"]):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert cli.main(argv) == 0, argv
        assert buf.getvalue().strip(), argv
