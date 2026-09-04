"""Divergence metrics over the responses to one identical request.

Character-level rather than token-level, deliberately: token metrics would
need provider-specific tokenizers, making scores harder for third parties to
reproduce (METHODOLOGY.md §3, §6)."""
import json
from collections import Counter


def first_divergence(texts):
    """Smallest index at which any two responses differ; length of the
    shortest response if one is a strict prefix of another; None if all
    responses are identical."""
    if len(set(texts)) <= 1:
        return None
    shortest = min(len(t) for t in texts)
    for i in range(shortest):
        if len({t[i] for t in texts}) > 1:
            return i
    return shortest


def canonical_json(text):
    """Parse as JSON and re-serialize canonically; None if unparseable."""
    try:
        return json.dumps(json.loads(text), sort_keys=True,
                          separators=(",", ":"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def score_samples(samples, expect="text"):
    if expect == "tool_call":
        return score_tool_call_samples(samples)
    ok = [s for s in samples if not s.get("error") and s.get("text")]
    texts = [s["text"] for s in ok]
    out = {"n": len(samples), "n_ok": len(texts),
           "errors": len(samples) - len(texts)}
    if not texts:
        return out
    counts = Counter(texts)
    top_n = counts.most_common(1)[0][1]
    out.update(
        distinct=len(counts),
        byte_identical=len(counts) == 1,
        mode_share=round(top_n / len(texts), 4),
        first_divergence_char=first_divergence(texts),
        fingerprints=sorted({s["fingerprint"] for s in samples
                             if s.get("fingerprint")}),
        model_versions=sorted({s["model_version"] for s in samples
                               if s.get("model_version")}),
    )
    if expect == "json":
        canon = [canonical_json(t) for t in texts]
        parsed = [c for c in canon if c is not None]
        out["json_parse_rate"] = round(len(parsed) / len(texts), 4)
        out["distinct_canonical_json"] = len(set(parsed)) if parsed else None
    return out


def score_tool_call_samples(samples):
    """Divergence metrics for expect: "tool_call" cases.

    Each non-error sample carries a "tool_call_outcome" tag written by
    probe.one_call: "tool_call" (with an ordered "tool_calls_normalized"
    list) when the model emitted at least one call, or "no_call" when the
    response was structurally valid but emitted none. Both outcomes are
    valid data points and both count toward n_ok: a model that calls the
    tool in half its responses and answers in plain text in the other half
    must not have the plain-text half silently excluded, which would
    report perfect determinism over only the calls that happened to match.
    A sample with no outcome tag (never produced by a successful parse)
    is treated as absent here as well, defensively.

    distinct, byte_identical, and mode_share are computed over the tagged
    outcome, so a run mixing "tool_call" and "no_call" responses, or two
    "tool_call" responses with different names, arguments, or call order,
    can never score as identical. tool_call_rate is the fraction of valid
    samples that emitted at least one call.

    When every valid sample is "no_call" (tool_call_rate == 0), there is
    no call payload to measure stability over: distinct, byte_identical,
    and mode_share are left out entirely rather than published as a claim
    about payload reproducibility that would not hold, since nothing was
    ever emitted to be reproducible. n, n_ok, errors, tool_call_rate,
    fingerprints, and model_versions are still reported.

    first_divergence_char, json_parse_rate, and distinct_canonical_json do
    not apply to a structured call list and are never reported here.
    """
    ok_keys = []
    n_tool_call = 0
    for s in samples:
        if s.get("error"):
            continue
        outcome = s.get("tool_call_outcome")
        if outcome == "tool_call":
            calls = s.get("tool_calls_normalized")
            if not calls:
                continue
            ok_keys.append(("tool_call", tuple((c[0], c[1]) for c in calls)))
            n_tool_call += 1
        elif outcome == "no_call":
            ok_keys.append(("no_call",))
        else:
            continue
    out = {"n": len(samples), "n_ok": len(ok_keys),
           "errors": len(samples) - len(ok_keys)}
    if not ok_keys:
        return out
    out.update(
        tool_call_rate=round(n_tool_call / len(ok_keys), 4),
        fingerprints=sorted({s["fingerprint"] for s in samples
                             if s.get("fingerprint")}),
        model_versions=sorted({s["model_version"] for s in samples
                               if s.get("model_version")}),
    )
    if n_tool_call == 0:
        return out
    counts = Counter(ok_keys)
    top_n = counts.most_common(1)[0][1]
    out.update(
        distinct=len(counts),
        byte_identical=len(counts) == 1,
        mode_share=round(top_n / len(ok_keys), 4),
    )
    return out
