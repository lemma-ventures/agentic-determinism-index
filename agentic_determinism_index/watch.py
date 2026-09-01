"""Continuous stack-ID watch with adaptive cost control.

Full reference scoring (burst+serial across cases) is expensive; run it on
a published cadence. Between score runs, maintainers still need to know when
a provider's stack ID drifts underneath them — that signal is cheap: one
short request per target.

Schedule (per target, independent):
  - start at ``min_interval_s`` (default 1 h)
  - after ``stable_after`` consecutive unchanged ticks, multiply interval by
    ``backoff`` (default 1.5), capped at ``max_interval_s`` (default 24 h)
  - on fingerprint/version change: emit a drift event and reset to min
  - each due time is jittered ±``jitter`` (default 20%) so checks are not
    perfectly periodic (reduces synchronized load and samples the day)

State and history live under ``runs/watch/`` and never touch ``runs/reference/``.
"""
from __future__ import annotations

import datetime
import json
import os
import random
import time

from .probe import one_call, utcnow
from .providers import make_provider


DEFAULTS = {
    "min_interval_s": 3600,       # 1 h when stack is byte-exact / unknown
    "max_interval_s": 86400,      # 24 h cap for stack-ID ticks
    "backoff": 1.5,
    "stable_after": 3,            # unchanged ticks before backing off
    "jitter": 0.20,
    # Full score re-runs are expensive. If the last scored run for a tuple was
    # not byte-exact, do not burn tokens re-probing it often — stack drift is
    # still watched cheaply; score cadence backs off hard.
    "non_exact_score_min_interval_s": 7 * 86400,   # 7 days
    "exact_score_min_interval_s": 86400,            # 1 day when byte-exact
}


def _load_json(path, default=None):
    if not os.path.isfile(path):
        return default
    with open(path) as f:
        return json.load(f)


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def _append_jsonl(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")


def _parse_iso(ts):
    if not ts:
        return None
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _target_key(target):
    label = target.get("label") or ""
    return f"{target['provider']}|{target['model']}|{label}"


def _stack_id(sample):
    fp = sample.get("fingerprint")
    mv = sample.get("model_version")
    parts = []
    if fp:
        parts.append(f"fp:{fp}")
    if mv:
        parts.append(f"mv:{mv}")
    return "|".join(parts) if parts else None


def next_interval_s(state_row, cfg=None):
    cfg = {**DEFAULTS, **(cfg or {})}
    streak = int(state_row.get("stable_streak") or 0)
    steps = max(0, streak - cfg["stable_after"] + 1) if streak >= cfg["stable_after"] else 0
    base = cfg["min_interval_s"] * (cfg["backoff"] ** steps)
    # Known non-byte-exact stacks: skip ahead toward the long end of the range
    # so we do not spend tokens re-checking divergence we already measured.
    if state_row.get("byte_exact") is False:
        base = max(base, cfg["min_interval_s"] * 4)
    return min(cfg["max_interval_s"], max(cfg["min_interval_s"], base))


def score_reprobe_due(state_row, now=None, cfg=None):
    """Whether a full score re-run is worth the tokens for this tuple.

    Byte-exact stacks may be re-scored daily (default). Non-exact stacks wait a
    week unless forced — repeated full bursts on a known-divergent stack waste
    spend without new information beyond the cheap stack-ID watch.
    """
    cfg = {**DEFAULTS, **(cfg or {})}
    now = now or time.time()
    last = state_row.get("last_score_epoch")
    if last is None:
        return True
    exact = state_row.get("byte_exact")
    if exact is True:
        gap = cfg["exact_score_min_interval_s"]
    elif exact is False:
        gap = cfg["non_exact_score_min_interval_s"]
    else:
        gap = cfg["exact_score_min_interval_s"]
    return now >= float(last) + gap


def ingest_score_hints(watch_dir, scores_rows, run_stamp=None):
    """Update watch state from a scored run so non-exact tuples back off."""
    state_path = os.path.join(watch_dir, "state.json")
    state = _load_json(state_path, default={"targets": {}, "config": dict(DEFAULTS)})
    state.setdefault("targets", {})
    now = time.time()
    for row in scores_rows or []:
        provider = row.get("provider")
        model = row.get("model")
        if not provider or not model:
            continue
        label = row.get("label") or ""
        tkey = f"{provider}|{model}|{label}"
        entry = state["targets"].setdefault(tkey, {
            "provider": provider,
            "model": model,
            "label": label,
            "stable_streak": 0,
        })
        # Aggregate: if any case is not byte-identical, the tuple is not exact.
        bi = row.get("byte_identical")
        if bi is False:
            entry["byte_exact"] = False
        elif bi is True and entry.get("byte_exact") is not False:
            entry["byte_exact"] = True
        entry["last_score_epoch"] = now
        entry["last_score_stamp"] = run_stamp
        if row.get("mode_share") is not None:
            entry["last_mode_share"] = row.get("mode_share")
    state["updated"] = utcnow()
    _write_json(state_path, state)
    return state


def schedule_next(now_ts, state_row, cfg=None, rng=None):
    cfg = {**DEFAULTS, **(cfg or {})}
    rng = rng or random
    interval = next_interval_s(state_row, cfg)
    jitter = 1.0 + rng.uniform(-cfg["jitter"], cfg["jitter"])
    due = now_ts + interval * jitter
    return due, interval


def is_due(state_row, now=None):
    now = now or time.time()
    due = state_row.get("next_due_epoch")
    if due is None:
        return True
    return now >= float(due)


def load_watch_history(history_path, limit=None):
    if not os.path.isfile(history_path):
        return []
    rows = []
    with open(history_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if limit is not None and limit > 0:
        rows = rows[-limit:]
    return rows


def build_watch_drift(history_rows):
    """Collapse jsonl watch samples into per-target drift timelines."""
    by_key = {}
    for row in history_rows:
        if row.get("error"):
            continue
        key = (row.get("provider"), row.get("model"), row.get("label") or "")
        if not key[0] or not key[1]:
            continue
        bucket = by_key.setdefault(key, {
            "provider": key[0],
            "model": key[1],
            "label": key[2],
            "points": [],
            "drift_count": 0,
            "last_stack_id": None,
        })
        sid = row.get("stack_id")
        if sid and bucket["last_stack_id"] and sid != bucket["last_stack_id"]:
            bucket["drift_count"] += 1
        if sid:
            bucket["last_stack_id"] = sid
        bucket["points"].append({
            "ts": row.get("ts"),
            "stack_id": sid,
            "fingerprint": row.get("fingerprint"),
            "model_version": row.get("model_version"),
            "latency_ms": row.get("latency_ms"),
        })

    out = []
    for bucket in sorted(by_key.values(), key=lambda b: (b["provider"], b["model"], b["label"])):
        latest = bucket["points"][-1] if bucket["points"] else {}
        out.append({
            "provider": bucket["provider"],
            "model": bucket["model"],
            "label": bucket["label"],
            "samples": len(bucket["points"]),
            "drift_count": bucket["drift_count"],
            "latest_stack_id": latest.get("stack_id"),
            "latest_fingerprint": latest.get("fingerprint"),
            "latest_model_version": latest.get("model_version"),
            "latest_ts": latest.get("ts"),
            "points": bucket["points"][-48:],  # cap for page size
        })
    return out


def run_tick(
    config_path,
    cases_path,
    watch_dir="runs/watch",
    force=False,
    cfg=None,
    rng=None,
):
    """Probe due targets once. Returns a summary dict."""
    cfg = {**DEFAULTS, **(cfg or {})}
    rng = rng or random
    config = _load_json(config_path)
    cases = _load_json(cases_path)["cases"]
    case = cases[0]
    state_path = os.path.join(watch_dir, "state.json")
    history_path = os.path.join(watch_dir, "history.jsonl")
    state = _load_json(state_path, default={"targets": {}, "config": cfg})
    state.setdefault("targets", {})
    state["config"] = {**cfg, **(state.get("config") or {})}
    cfg = {**DEFAULTS, **state["config"]}

    now = time.time()
    now_iso = utcnow()
    summary = {
        "ts": now_iso,
        "probed": [],
        "skipped": [],
        "drift_events": [],
        "errors": [],
    }

    for target in config.get("targets") or []:
        key_env = target.get("api_key_env")
        if key_env and not os.environ.get(key_env):
            summary["skipped"].append({
                "target": _target_key(target),
                "reason": f"{key_env} not set",
            })
            continue

        tkey = _target_key(target)
        row = state["targets"].setdefault(tkey, {
            "provider": target["provider"],
            "model": target["model"],
            "label": target.get("label") or "",
            "stable_streak": 0,
            "last_stack_id": None,
            "last_fingerprint": None,
            "last_model_version": None,
            "last_ts": None,
            "next_due_epoch": None,
            "interval_s": cfg["min_interval_s"],
            "ticks": 0,
            "drifts": 0,
        })

        if not force and not is_due(row, now):
            summary["skipped"].append({
                "target": tkey,
                "reason": "not_due",
                "next_due_epoch": row.get("next_due_epoch"),
                "interval_s": row.get("interval_s"),
            })
            continue

        try:
            provider = make_provider(target)
            sample = one_call(provider, case, "watch")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            summary["errors"].append({"target": tkey, "error": err})
            _append_jsonl(history_path, {
                "ts": now_iso,
                "provider": target["provider"],
                "model": target["model"],
                "label": target.get("label") or "",
                "error": err,
            })
            due, interval = schedule_next(now, row, cfg, rng)
            row["next_due_epoch"] = due
            row["interval_s"] = interval
            continue

        if sample.get("error"):
            summary["errors"].append({"target": tkey, "error": sample["error"]})
            _append_jsonl(history_path, {
                "ts": sample.get("ts") or now_iso,
                "provider": target["provider"],
                "model": target["model"],
                "label": target.get("label") or "",
                "error": sample["error"],
                "latency_ms": sample.get("latency_ms"),
            })
            due, interval = schedule_next(now, row, cfg, rng)
            row["next_due_epoch"] = due
            row["interval_s"] = interval
            continue

        sid = _stack_id(sample)
        prev = row.get("last_stack_id")
        drifted = bool(prev and sid and sid != prev)
        if drifted:
            row["stable_streak"] = 0
            row["drifts"] = int(row.get("drifts") or 0) + 1
            event = {
                "ts": sample.get("ts") or now_iso,
                "provider": target["provider"],
                "model": target["model"],
                "label": target.get("label") or "",
                "from_stack_id": prev,
                "to_stack_id": sid,
                "fingerprint": sample.get("fingerprint"),
                "model_version": sample.get("model_version"),
            }
            summary["drift_events"].append(event)
            _append_jsonl(os.path.join(watch_dir, "drift-events.jsonl"), event)
        else:
            if sid and sid == prev:
                row["stable_streak"] = int(row.get("stable_streak") or 0) + 1
            elif sid and not prev:
                row["stable_streak"] = 1

        row["last_stack_id"] = sid
        row["last_fingerprint"] = sample.get("fingerprint")
        row["last_model_version"] = sample.get("model_version")
        row["last_ts"] = sample.get("ts") or now_iso
        row["ticks"] = int(row.get("ticks") or 0) + 1
        due, interval = schedule_next(now, row, cfg, rng)
        row["next_due_epoch"] = due
        row["interval_s"] = interval

        rec = {
            "ts": sample.get("ts") or now_iso,
            "provider": target["provider"],
            "model": target["model"],
            "label": target.get("label") or "",
            "stack_id": sid,
            "fingerprint": sample.get("fingerprint"),
            "model_version": sample.get("model_version"),
            "latency_ms": sample.get("latency_ms"),
            "text_sha256": sample.get("sha256"),
            "drifted": drifted,
            "stable_streak": row["stable_streak"],
            "next_interval_s": interval,
        }
        _append_jsonl(history_path, rec)
        summary["probed"].append(rec)

    state["updated"] = now_iso
    _write_json(state_path, state)
    _write_json(os.path.join(watch_dir, "last-tick.json"), summary)
    return summary


def format_tick_summary(summary):
    lines = [f"watch tick @ {summary.get('ts')}"]
    lines.append(f"  probed: {len(summary.get('probed') or [])}")
    lines.append(f"  skipped: {len(summary.get('skipped') or [])}")
    lines.append(f"  errors: {len(summary.get('errors') or [])}")
    lines.append(f"  drift_events: {len(summary.get('drift_events') or [])}")
    for d in summary.get("drift_events") or []:
        lines.append(
            f"  DRIFT {d['provider']}/{d['model']}: "
            f"{d.get('from_stack_id')} -> {d.get('to_stack_id')}"
        )
    for p in summary.get("probed") or []:
        lines.append(
            f"  ok {p['provider']}/{p['model']} "
            f"stack={p.get('stack_id') or 'n/a'} "
            f"next={int(p.get('next_interval_s') or 0)}s "
            f"streak={p.get('stable_streak')}"
        )
    for e in summary.get("errors") or []:
        lines.append(f"  err {e['target']}: {e['error']}")
    return "\n".join(lines) + "\n"
