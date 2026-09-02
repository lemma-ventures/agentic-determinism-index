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
