"""``python3 -m agentic_determinism_index mcp`` - the leaderboard as MCP tools.

A stdio Model Context Protocol server (JSON-RPC 2.0, one message per line,
no dependencies) so an agent - a router like captain, a coding assistant, a
pipeline - can ask which serving tuples are reproducible before choosing
one. Three tools, all read-only:

  adi_leaderboard(green_only=false, provider="", limit=50)
      ranked serving tuples with mode share, streak, green flag and the
      request pins (provider_prefs) that reproduce each tuple
  adi_tuple(provider, model, label="")
      one tuple's row, or the rows for every pin of that (provider, model)
  adi_green(provider="")
      only the tuples whose latest scored appearance was byte-exact

Source: ``--feed <url|path>`` (default: the published leaderboard.json),
or ``--run-root runs/reference`` to build the feed from local runs.
"""

import json
import sys

from . import feed as feedmod

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "adi_leaderboard",
        "description": "Agentic Determinism Index: serving tuples (provider, model, pin) ranked by reproducibility, with mean mode share, byte-exact streak, the green flag and the provider_prefs that reproduce the tuple.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "green_only": {"type": "boolean", "description": "only tuples whose latest scored appearance was fully byte-exact"},
                "provider": {"type": "string", "description": "filter by ADI provider id (openrouter, nvidia_nim, openai, anthropic, gemini, openai_compatible, huggingface)"},
                "limit": {"type": "integer", "description": "max rows (default 50)"},
            },
        },
    },
    {
        "name": "adi_tuple",
        "description": "One serving tuple's reproducibility row (provider + model, optionally the pin label); without a label, every measured pin of that provider/model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string"},
                "model": {"type": "string"},
                "label": {"type": "string"},
            },
            "required": ["provider", "model"],
        },
    },
    {
        "name": "adi_green",
        "description": "The serving tuples that are green right now (latest scored appearance byte-exact), best first, with their provider_prefs.",
        "inputSchema": {
            "type": "object",
            "properties": {"provider": {"type": "string"}},
        },
    },
]


class Server:
    def __init__(self, source=None, run_root=None, config_dir="configs"):
        self.source = source
        self.run_root = run_root
        self.config_dir = config_dir
        self._feed = None

    def feed(self):
        if self._feed is None:
            if self.run_root:
                from .site import build_payload
                payload = build_payload(run_root=self.run_root)
                self._feed = feedmod.build_feed(payload, config_dir=self.config_dir)
            else:
                self._feed = feedmod.read_feed(self.source)
        return self._feed

    # ---- tools -----------------------------------------------------------
    def tool(self, name, args):
        args = args or {}
        rows = list(self.feed().get("tuples") or [])
        provider = (args.get("provider") or "").strip().lower()
        if provider:
            rows = [r for r in rows if (r.get("provider") or "").lower() == provider]
        if name == "adi_leaderboard":
            if args.get("green_only"):
                rows = [r for r in rows if r.get("green")]
            limit = int(args.get("limit") or 50)
            return rows[:limit]
        if name == "adi_green":
            return [r for r in rows if r.get("green")]
        if name == "adi_tuple":
            model = (args.get("model") or "").strip().lower()
            label = (args.get("label") or "").strip()
            out = [r for r in rows if (r.get("model") or "").lower() == model]
            if label:
                out = [r for r in out if (r.get("label") or "") == label]
            return out
        raise KeyError(name)

    # ---- JSON-RPC --------------------------------------------------------
    def handle(self, msg):
        method = msg.get("method")
        mid = msg.get("id")
        if method == "initialize":
            return self._result(mid, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agentic-determinism-index", "version": "0.1"},
            })
        if method == "notifications/initialized" or method is None:
            return None
        if method == "ping":
            return self._result(mid, {})
        if method == "tools/list":
            return self._result(mid, {"tools": TOOLS})
        if method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name")
            try:
                rows = self.tool(name, params.get("arguments") or {})
            except KeyError:
                return self._error(mid, -32602, f"unknown tool {name!r}")
            except Exception as e:  # noqa: BLE001 - reported to the caller, never crashes the server
                return self._result(mid, {"content": [{"type": "text", "text": f"adi: {e}"}], "isError": True})
            meta = self.feed()
            text = json.dumps({
                "run_stamp": meta.get("run_stamp"),
                "generated_at": meta.get("generated_at"),
                "rows": rows,
            }, indent=1)
            return self._result(mid, {"content": [{"type": "text", "text": text}]})
        if mid is None:
            return None
        return self._error(mid, -32601, f"method not found: {method}")

    @staticmethod
    def _result(mid, result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    @staticmethod
    def _error(mid, code, message):
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def serve(server, inp=None, out=None):
    inp = inp or sys.stdin
    out = out or sys.stdout
    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = server.handle(msg)
        if reply is not None:
            out.write(json.dumps(reply) + "\n")
            out.flush()
