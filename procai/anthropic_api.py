"""受講者が各自のキーで回す呼び先 (Messages API・標準ライブラリの urllib だけ)。

- キーは環境変数 ANTHROPIC_API_KEY から読むだけ。表示しない・記録に書かない。
- 道具あり (条件 B/C) は tool use の往復をここで回す (上限 MAX_TURNS 往復)。
- モデルと effort は同梱の記録と同じ既定 (claude-opus-5-5・high)。費用が出るので、回す前に件数を確かめる。
テストでは urlopen を差し替えて、本物は呼ばない。
"""
import json
import os
import time
import urllib.request

from . import tools

URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
MAX_TOKENS = 16000
MAX_TURNS = 30
SYSTEM = "日本語で答える。最後に、問題文で指定された形の JSON だけを出力する。"
_urlopen = urllib.request.urlopen


def _post(body, key):
    req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    with _urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def call(user, mode=None, model=DEFAULT_MODEL, effort=DEFAULT_EFFORT):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY が環境変数に無い (各自のキーを置く。キーなしなら --provider replay で記録を再生)")
    msgs = [{"role": "user", "content": user}]
    body = {"model": model, "max_tokens": MAX_TOKENS, "system": SYSTEM, "messages": msgs}
    if effort:
        body["output_config"] = {"effort": effort}
    if mode:
        body["tools"] = [{"name": s["name"], "description": s["description"], "input_schema": tools.input_schema(s)}
                         for s in tools.SPECS]
    trace, usage, turns, t0 = [], {"input_tokens": 0, "output_tokens": 0}, 0, time.time()
    text = ""
    while True:
        turns += 1
        r = _post(body, key)
        for k in usage:
            usage[k] += (r.get("usage") or {}).get(k, 0) or 0
        content = r.get("content") or []
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        if texts:
            text = texts[-1]
        uses = [b for b in content if b.get("type") == "tool_use"]
        if r.get("stop_reason") != "tool_use" or not uses or turns >= MAX_TURNS:
            break
        msgs.append({"role": "assistant", "content": content})
        results = []
        for u in uses:
            out, err = tools.call(u["name"], u.get("input") or {}, mode)
            trace.append({"tool": u["name"], "input": u.get("input"), "is_error": err, "out_chars": len(out)})
            results.append({"type": "tool_result", "tool_use_id": u["id"], "content": out, "is_error": err})
        msgs.append({"role": "user", "content": results})
    return {"provider": "anthropic", "model": model, "effort": effort, "text": text, "trace": trace, "turns": turns,
            "usage": usage, "seconds": round(time.time() - t0, 2), "error": None}
