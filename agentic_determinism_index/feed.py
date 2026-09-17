"""Machine-readable leaderboard: ``leaderboard.json`` beside ``index.html``.

The HTML page is for people. A router that wants to *choose* a serving tuple
(``captain`` picks the leg to run a task on) needs the same facts as data:
which (provider, model, pin) tuples are byte-exact right now, how long they
have stayed that way, and the exact request pins that reproduce the tuple
(``provider_prefs``: the OpenRouter ``provider.order`` / ``allow_fallbacks``
the reference config sends). Everything here is derived from the same
payload the page renders; nothing is judged that the page does not show.

``green`` is the one word the feed adds: a tuple is green when its latest
scored appearance was fully byte-exact (streak >= 1). It is a snapshot fact
about a serving stack, not a certification, and it can turn red on the next
reference run.
"""

import glob
import json
import os
import urllib.request

FEED_NAME = "leaderboard.json"
FEED_VERSION = 1
DEFAULT_FEED_URL = "https://lemma-ventures.github.io/agentic-determinism-index/leaderboard.json"


def _tuple_key(provider, model, label):
    return ((provider or "").strip(), (model or "").strip(), (label or "").strip())


def load_provider_prefs(config_dir="configs"):
    """Map every (provider, model, label) a config names to its request pins."""
    prefs = {}
    for path in sorted(glob.glob(os.path.join(config_dir, "*.json"))):
        try:
            with open(path) as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            continue
        targets = cfg.get("targets") if isinstance(cfg, dict) else cfg
        if not isinstance(targets, list):
            continue
        for t in targets:
            if not isinstance(t, dict):
                continue
            key = _tuple_key(t.get("provider"), t.get("model"), t.get("label"))
            entry = {}
            if isinstance(t.get("provider_prefs"), dict):
                entry["provider_prefs"] = t["provider_prefs"]
            if t.get("base_url"):
                entry["base_url"] = t["base_url"]
            if key not in prefs or entry:
                prefs[key] = entry
    return prefs


def build_feed(payload, config_dir="configs"):
    """The feed document from a site payload (``site.build_payload``)."""
    prefs = load_provider_prefs(config_dir) if config_dir else {}
    tuples = []
    for entry in payload.get("leaders") or []:
        key = _tuple_key(entry.get("provider"), entry.get("model"), entry.get("label"))
        pins = prefs.get(key, {})
        streak = int(entry.get("streak") or 0)
        tuples.append({
            "provider": key[0],
            "model": key[1],
            "label": key[2],
            "display": entry.get("display") or (key[2] or f"{key[0]}/{key[1]}"),
            "rank": entry.get("rank"),
            "medal": entry.get("medal") or "",
            "score": entry.get("score"),
            "mean_mode_share": entry.get("mean_mode_share"),
            "exact_match_rate": entry.get("exact_match_rate"),
            "runs_seen": int(entry.get("runs_seen") or 0),
            "deterministic_runs": int(entry.get("deterministic_runs") or 0),
            "streak": streak,
            "green": streak >= 1,
            "score_as_of": entry.get("score_as_of") or payload.get("run_stamp") or "",
            "provider_prefs": pins.get("provider_prefs"),
            "base_url": pins.get("base_url"),
        })
    return {
        "feed_version": FEED_VERSION,
        "generated_at": payload.get("generated_at") or "",
        "run_stamp": payload.get("run_stamp") or "",
        "n_runs": payload.get("n_runs") or 0,
        "methodology": "METHODOLOGY.md v0.1 - green = latest scored appearance fully byte-exact; a snapshot, not a certification",
        "tuples": tuples,
    }


def write_feed(out_path, payload, config_dir="configs"):
    doc = build_feed(payload, config_dir=config_dir)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write("\n")
    return out_path


def read_feed(source=None, timeout=10):
    """Read a feed from a URL, a file, or the published default."""
    src = source or DEFAULT_FEED_URL
    if src.startswith("http://") or src.startswith("https://"):
        with urllib.request.urlopen(src, timeout=timeout) as r:  # noqa: S310 - the caller names the URL
            return json.loads(r.read().decode("utf-8"))
    with open(src) as f:
        return json.load(f)
