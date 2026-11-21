"""同梱の記録を作った呼び先: Claude Agent SDK をプランのログインで呼ぶ (★受講者向けの道ではない★)。

受講者は記録 (experiment/results/) を replay で再生するか、各自のキーで anthropic を使う。
- 組み込みの道具 (Read・Bash など) は外す (tools=[])。B/C だけ procai.tools の読み取り専用 12 個と電卓を MCP で見せる
  (B は mode=raw、C は mode=guarded = 渡さない層の後ろ)。
- 手元の設定は読まない (setting_sources=[])・MCP は渡したものだけ (strict_mcp_config)・作業フォルダは空の一時フォルダ。
- 🔴 キーは渡さない: 子プロセスの ANTHROPIC_API_KEY を空にしてログインで動かす (キーは読まない・表示しない)。
- 道具を後から読む仕組み (tool search) は切る (ENABLE_TOOL_SEARCH=false)。
テストでは claude_agent_sdk を差し替えて、本物は呼ばない。
"""
import asyncio
import tempfile
import time
import os

from . import tools

PROVIDER_NAME = "agent-sdk"
DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
MAX_TURNS_TOOLS = 30
SERVER = "procai"
SYSTEM = "日本語で答える。最後に、問題文で指定された形の JSON だけを出力する。"


def call(user, mode=None, model=DEFAULT_MODEL, effort=DEFAULT_EFFORT):
    """mode=None は一発 (道具なし)。"raw"/"guarded" は道具あり。"""
    os.environ.pop("ANTHROPIC_API_KEY", None)
    import claude_agent_sdk as sdk

    trace = []

    def handler_for(name):
        async def h(args):
            out, err = tools.call(name, args, mode)
            trace.append({"tool": name, "input": args, "is_error": err, "out_chars": len(out)})
            return {"content": [{"type": "text", "text": out}], "is_error": err}
        return h

    servers, allowed = {}, []
    if mode:
        ts = [sdk.SdkMcpTool(name=s["name"], description=s["description"], input_schema=tools.input_schema(s),
                             handler=handler_for(s["name"])) for s in tools.SPECS]
        servers = {SERVER: sdk.create_sdk_mcp_server(SERVER, tools=ts)}
        allowed = [f"mcp__{SERVER}__{s['name']}" for s in tools.SPECS]
    opts = sdk.ClaudeAgentOptions(
        model=model, system_prompt=SYSTEM, tools=[], mcp_servers=servers, allowed_tools=allowed,
        strict_mcp_config=True, setting_sources=[], max_turns=MAX_TURNS_TOOLS if mode else 1,
        cwd=tempfile.mkdtemp(prefix="procai_sdk_"),
        env={"ANTHROPIC_API_KEY": "", "ENABLE_TOOL_SEARCH": "false"},
        **({"effort": effort} if effort else {}))
    texts, res, seen_model = [], {}, []

    async def main():
        async for m in sdk.query(prompt=user, options=opts):
            if isinstance(m, sdk.AssistantMessage):
                if getattr(m, "model", None):
                    seen_model.append(m.model)
                for b in m.content:
                    if isinstance(b, sdk.TextBlock):
                        texts.append(b.text)
            elif isinstance(m, sdk.ResultMessage):
                res.update(usage=m.usage or {}, api_equiv_usd=m.total_cost_usd, turns=m.num_turns,
                           is_error=m.is_error, result=m.result, terminal=getattr(m, "terminal_reason", None))

    t0 = time.time()
    asyncio.run(main())
    text = texts[-1] if texts else (res.get("result") or "")
    u = res.get("usage") or {}
    return {"provider": PROVIDER_NAME, "model": model, "effort": effort,
            "model_seen": seen_model[-1] if seen_model else None, "text": text, "trace": trace,
            "turns": res.get("turns"), "api_equiv_usd": res.get("api_equiv_usd"),
            "usage": {k: u.get(k) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                            "cache_creation_input_tokens") if k in u},
            "seconds": round(time.time() - t0, 2),
            "error": (res.get("result") or "")[:300] if res.get("is_error") else None,
            "terminal": res.get("terminal")}
