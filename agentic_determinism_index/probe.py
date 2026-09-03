"""Probe loop: fire N identical requests (concurrent burst + spaced serial)
and record raw samples. Transcripts keep the exact response text plus its
SHA-256 so published scores can be re-derived and verified."""
import concurrent.futures
import datetime
import hashlib
import time

from .toolcalls import NO_TOOL_CALL, ToolCallParseError, normalize_tool_calls


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _is_openai_style_tools(tools):
    """Structural check for the neutral tool-definition shape this harness
    accepts in case files: an OpenAI Chat Completions-style function tool
    list. Provider adapters translate this into their own wire format."""
    if not isinstance(tools, list) or not tools:
        return False
    for t in tools:
        if not isinstance(t, dict) or t.get("type") != "function":
            return False
        fn = t.get("function")
        if not isinstance(fn, dict):
            return False
        name = fn.get("name")
        if not isinstance(name, str) or not name:
            return False
    return True


def validate_cases(cases):
    """Enforce the expect/tools contract (METHODOLOGY.md, tool call
    section) before any probe runs: a case that specifies 'tools' must
    declare expect == "tool_call" with a usable OpenAI-style function tool
    list, and a tool_call case must specify 'tools'. Any other combination
    is rejected outright rather than silently downgraded to a text case.
    """
    for c in cases or []:
        if not isinstance(c, dict):
            raise SystemExit(f"case is not an object: {c!r}")
        cid = c.get("id", "?")
        expect = c.get("expect", "text")
        tools = c.get("tools")
        if expect == "tool_call":
            if not tools:
                raise SystemExit(
                    f"case {cid} has expect == 'tool_call' but no 'tools'; "
                    "a tool_call case requires a usable tool definition"
                )
            if not _is_openai_style_tools(tools):
                raise SystemExit(
                    f"case {cid} 'tools' is not a valid OpenAI-style "
                    "function tool list (each entry needs "
                    "type == 'function' and function.name)"
                )
        elif tools:
            raise SystemExit(
                f"case {cid} specifies 'tools' but expect != 'tool_call'; "
                "unsupported combination (see METHODOLOGY.md)"
            )


def one_call(provider, case, mode):
    rec = {"ts": utcnow(), "mode": mode}
    t0 = time.monotonic()
    expect = case.get("expect", "text")
    try:
        r = provider.call(case)
        if expect == "tool_call":
            rec["text"] = r.get("text") or ""
            rec["tool_calls_raw"] = r.get("tool_calls")
            try:
                outcome = normalize_tool_calls(r.get("tool_calls"))
            except ToolCallParseError as e:
                rec["error"] = f"malformed: {e}"
            else:
                if outcome is NO_TOOL_CALL:
                    rec["tool_call_outcome"] = "no_call"
                else:
                    rec["tool_call_outcome"] = "tool_call"
                    rec["tool_calls_normalized"] = [list(c) for c in outcome]
                rec.update(
                    fingerprint=r.get("fingerprint"),
                    model_version=r.get("model_version"),
                )
        else:
            txt = r.get("text") or ""
            if not txt:
                rec["error"] = "unsupported: empty completion (tool call or similar)"
            else:
                rec.update(
                    text=txt,
                    sha256=sha256(txt),
                    fingerprint=r.get("fingerprint"),
                    model_version=r.get("model_version"),
                )
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    rec["latency_ms"] = round((time.monotonic() - t0) * 1000)
    return rec


def run_probe(provider, case, burst=10, serial=3, gap=60):
    samples = []
    if burst:
        with concurrent.futures.ThreadPoolExecutor(max_workers=burst) as ex:
            futures = [ex.submit(one_call, provider, case, "burst")
                       for _ in range(burst)]
            samples.extend(f.result() for f in futures)
    for i in range(serial):
        if i or burst:
            time.sleep(gap)
        samples.append(one_call(provider, case, "serial"))
    return samples
