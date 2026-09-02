"""Generate a static website for published Agentic Determinism Index results."""

import datetime
import hashlib
import html
import json
import os
import re
from collections import defaultdict


MEDALS = {1: "1st", 2: "2nd", 3: "3rd"}
# Crockford-ish alphabet (no i/l/o/u) for short stack / run ids.
_ID_ALPHABET = "abcdefghjkmnpqrstvwxyz23456789"


def _safe_read_json(path):
    with open(path) as f:
        return json.load(f)


def load_scores(run_dir):
    scores = os.path.join(run_dir, "scores.json")
    if not os.path.isfile(scores):
        raise FileNotFoundError(f"scores.json not found under {run_dir}")
    return _safe_read_json(scores)


def load_manifest(run_dir):
    manifest = os.path.join(run_dir, "manifest.json")
    return _safe_read_json(manifest) if os.path.isfile(manifest) else {}


def latest_scored_run(run_root):
    if not os.path.isdir(run_root):
        return None
    candidates = []
    for name in sorted(os.listdir(run_root)):
        path = os.path.join(run_root, name)
        if not os.path.isdir(path):
            continue
        scores = os.path.join(path, "scores.json")
        if os.path.isfile(scores):
            candidates.append(path)
    if not candidates:
        return None
    return candidates[-1]


def _list_scored_runs(run_root):
    if not os.path.isdir(run_root):
        return []
    runs = []
    for name in sorted(os.listdir(run_root)):
        path = os.path.join(run_root, name)
        if not os.path.isdir(path):
            continue
        scores = os.path.join(path, "scores.json")
        if os.path.isfile(scores):
            runs.append(path)
    return runs


def _norm_stack_values(values):
    return sorted({str(v).strip() for v in (values or []) if v})


def _summarize_run_rows(rows):
    providers = set()
    models = set()
    cases = set()
    n_total = 0
    n_ok_total = 0
    errors_total = 0
    scored_rows = 0

    for row in rows:
        provider = row.get("provider")
        model = row.get("model")
        case = row.get("case")
        if provider:
            providers.add(provider)
        if model:
            models.add(model)
        if case:
            cases.add(case)

        n = row.get("n")
        if isinstance(n, (int, float)):
            n_total += n

        n_ok = row.get("n_ok")
        if isinstance(n_ok, (int, float)):
            n_ok_total += n_ok

        errors = row.get("errors")
        if isinstance(errors, (int, float)):
            errors_total += errors

        if row.get("mode_share") is not None:
            scored_rows += 1

    success_rate = round(n_ok_total / n_total, 4) if n_total else None
    return {
        "providers": len(providers),
        "models": len(models),
        "cases": len(cases),
        "probe_rows": len(rows),
        "scored_rows": scored_rows,
        "requests": int(n_total),
        "non_error_requests": int(n_ok_total),
        "errors": int(errors_total),
        "success_rate": success_rate,
    }


def _collect_run_stack_points(run_dir):
    rows = load_scores(run_dir)
    by_target = defaultdict(lambda: {
        "provider": "",
        "model": "",
        "fingerprints": set(),
        "model_versions": set(),
    })

    for row in rows:
        provider = row.get("provider")
        model = row.get("model")
        if not provider or not model:
            continue

        key = (provider, model)
        fp = by_target[key]["fingerprints"]
        fv = by_target[key]["model_versions"]
        fp.update(_norm_stack_values(row.get("fingerprints")))
        fv.update(_norm_stack_values(row.get("model_versions")))
        by_target[key]["provider"] = provider
        by_target[key]["model"] = model

    return {
        key: {
            "provider": data["provider"],
            "model": data["model"],
            "fingerprints": sorted(data["fingerprints"]),
            "model_versions": sorted(data["model_versions"]),
        }
        for key, data in by_target.items()
    }


def build_stack_drift(run_root):
    if not run_root or not os.path.isdir(run_root):
        return []

    all_runs = _list_scored_runs(run_root)
    if len(all_runs) < 2:
        return []

    history = defaultdict(list)
    for run_dir in all_runs:
        stamp = os.path.basename(run_dir)
        points = _collect_run_stack_points(run_dir)
        for item in points.values():
            if not item["fingerprints"] and not item["model_versions"]:
                continue
            history[(item["provider"], item["model"])].append({
                "run_stamp": stamp,
                "fingerprints": item["fingerprints"],
                "model_versions": item["model_versions"],
            })

    out = []
    for (provider, model), points in sorted(history.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        drift_count = 0
        prev_fps = None
        prev_mvs = None
        normalized = []
        for point in points:
            fps = point["fingerprints"]
            mvs = point["model_versions"]
            if prev_fps is not None and (fps != prev_fps or mvs != prev_mvs):
                drift_count += 1
            prev_fps, prev_mvs = fps, mvs
            normalized.append(point)

        out.append({
            "provider": provider,
            "model": model,
            "runs": normalized,
            "drift_count": drift_count,
            "latest_fingerprints": points[-1]["fingerprints"],
            "latest_model_versions": points[-1]["model_versions"],
        })
    return out


def build_first_metrics(run_dir, run_root=None):
    rows = load_scores(run_dir)
    summary = _summarize_run_rows(rows)
    if run_root is None:
        run_root = os.path.dirname(run_dir)
    drift = build_stack_drift(run_root)
    return {
        "summary": summary,
        "stack_drift": drift,
    }


def _as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _tuple_key(row):
    """Serving tuple for ranking: provider + model + optional pin label."""
    provider = row.get("provider") or ""
    model = row.get("model") or "unknown"
    label = (row.get("label") or "").strip()
    return (provider, model, label)


def _run_tuple_byte_exact(rows):
    """True when every scored case for a tuple in one run is byte-identical.

    Returns dict keyed by ``_tuple_key`` → bool. Unscored (no mode_share) rows
    are ignored; a tuple with no scored cases is omitted.
    """
    by_key = {}
    for row in rows or []:
        if not row.get("provider"):
            continue
        if _as_float(row.get("mode_share")) is None:
            continue
        key = _tuple_key(row)
        bucket = by_key.setdefault(key, {"any": False, "all_exact": True})
        bucket["any"] = True
        if not row.get("byte_identical"):
            bucket["all_exact"] = False
    return {k: v["all_exact"] for k, v in by_key.items() if v["any"]}


def tuple_deterministic_survival(run_root):
    """Across scored reference runs, how often each serving tuple stayed byte-exact.

    For each tuple key returns::
        {
          "runs_seen": N,             # reference runs that scored this tuple
          "deterministic_runs": M,    # of those, fully byte-exact
          "streak": S,                # consecutive byte-exact ending at latest run
        }
    Streak resets when the tuple is missing from a later run or fails byte-exact.
    """
    survival = {}
    for path in _list_scored_runs(run_root):
        try:
            rows = load_scores(path)
        except (OSError, ValueError, TypeError):
            continue
        exact_map = _run_tuple_byte_exact(rows)
        seen_this_run = set(exact_map)

        # Advance streak for tuples present this run; reset others that were active.
        for key, exact in exact_map.items():
            s = survival.setdefault(key, {
                "runs_seen": 0,
                "deterministic_runs": 0,
                "streak": 0,
            })
            s["runs_seen"] += 1
            if exact:
                s["deterministic_runs"] += 1
                s["streak"] += 1
            else:
                s["streak"] = 0

        # Missing from this run breaks the streak (survived consecutive window).
        for key, s in survival.items():
            if key not in seen_this_run:
                s["streak"] = 0
    return survival


def aggregate_leaderboard(rows):
    """Rank scored serving tuples. Rows with n_ok == 0 / no mode_share are
    excluded so failed probes (EOL models, missing endpoints) do not take
    medals or pollute the board with zeros."""
    tuples = {}
    for row in rows:
        provider = row.get("provider")
        if not provider:
            continue
        mode_share = _as_float(row.get("mode_share"))
        # Unscored probe (all errors): skip entirely.
        if mode_share is None:
            continue
        key = _tuple_key(row)
        model = row.get("model") or "unknown"
        label = (row.get("label") or "").strip()
        stats = tuples.setdefault(key, {
            "provider": provider,
            "model": model,
            "label": label,
            "rows": 0,
            "mode_sum": 0.0,
            "mode_rows": 0,
            "exact_sum": 0,
            "exact_rows": 0,
            "distinct_sum": 0.0,
            "distinct_rows": 0,
        })

        stats["rows"] += 1
        stats["mode_sum"] += mode_share
        stats["mode_rows"] += 1
        stats["exact_rows"] += 1
        if row.get("byte_identical"):
            stats["exact_sum"] += 1

        distinct = _as_float(row.get("distinct"))
        if distinct is not None:
            stats["distinct_sum"] += distinct
            stats["distinct_rows"] += 1

    ranked = []
    for s in tuples.values():
        mode_rows = s["mode_rows"]
        if mode_rows == 0:
            continue
        exact_rows = s["exact_rows"]
        distinct_rows = s["distinct_rows"]
        mean_mode = s["mode_sum"] / mode_rows
        exact_rate = s["exact_sum"] / exact_rows if exact_rows else 0.0
        mean_distinct = s["distinct_sum"] / distinct_rows if distinct_rows else None
        if mean_distinct is None:
            stability = 0.0
        else:
            stability = 1.0 / (1.0 + max(0.0, mean_distinct - 1.0))
        score = (0.70 * mean_mode) + (0.25 * exact_rate) + (0.05 * stability)
        score *= 100

        display = s["label"] or f"{s['provider']}/{s['model']}"
        ranked.append({
            "provider": s["provider"],
            "model": s["model"],
            "label": s["label"],
            "display": display,
            "rows": s["rows"],
            "mean_mode_share": round(mean_mode, 4),
            "exact_match_rate": round(exact_rate, 4),
            "mean_distinct": round(mean_distinct, 4) if mean_distinct is not None else None,
            "score": round(score, 2),
            "deterministic_runs": 1 if exact_rate >= 0.999 else 0,
            "runs_seen": 1,
            "streak": 1 if exact_rate >= 0.999 else 0,
            # Back-compat for older HTML payload consumers / tests.
            "models": [{
                "name": s["model"],
                "rows": s["rows"],
                "mean_mode_share": round(mean_mode, 4),
                "exact_match": round(exact_rate, 4),
            }],
        })

    ranked.sort(key=lambda x: (x["score"], x["mean_mode_share"]), reverse=True)
    for i, entry in enumerate(ranked):
        entry["rank"] = i + 1
        entry["medal"] = MEDALS.get(i + 1, "")
    return ranked


def apply_survival(leaders, survival):
    """Attach cross-run deterministic survival counts onto leaderboard rows."""
    for entry in leaders or []:
        key = (
            entry.get("provider") or "",
            entry.get("model") or "unknown",
            (entry.get("label") or "").strip(),
        )
        s = (survival or {}).get(key) or {}
        entry["runs_seen"] = int(s.get("runs_seen") or entry.get("runs_seen") or 1)
        entry["deterministic_runs"] = int(
            s.get("deterministic_runs")
            if s.get("deterministic_runs") is not None
            else entry.get("deterministic_runs") or 0
        )
        entry["streak"] = int(s.get("streak") if s.get("streak") is not None else entry.get("streak") or 0)
    return leaders


def short_stack_id(text, length=12):
    """Opaque short id for URLs, e.g. qert7m2k...n4vw (shown as qert…n4vw)."""
    digest = hashlib.sha256(str(text).encode("utf-8")).digest()
    n = int.from_bytes(digest, "big")
    chars = []
    base = len(_ID_ALPHABET)
    for _ in range(length):
        chars.append(_ID_ALPHABET[n % base])
        n //= base
    return "".join(chars)


def display_stack_id(sid):
    if not sid or len(sid) < 8:
        return sid or ""
    return f"{sid[:4]}…{sid[-4:]}"


def _format_float(v):
    return f"{v:.4f}" if v is not None else "n/a"


def _format_pct(v):
    if v is None:
        return "n/a"
    return f"{100.0 * float(v):.0f}%"


def _short_dt(iso):
    """ISO timestamp → compact UTC display (YYYY-MM-DD HH:MM UTC)."""
    if not iso:
        return ""
    s = str(iso).replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt = dt.astimezone(datetime.timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return str(iso)[:16]


def _byte_exact_cell(rate):
    """Human label for average byte-identity across cases."""
    if rate is None:
        return '<span class="pill pill-na">n/a</span>', ""
    r = float(rate)
    if r >= 0.999:
        return '<span class="pill pill-yes">Yes · byte-exact</span>', "row-exact"
    if r <= 0.001:
        return '<span class="pill pill-no">No</span>', ""
    return (
        f'<span class="pill pill-partial">Partial · {_format_pct(r)}</span>',
        "",
    )


def render_html(payload):
    title = html.escape(payload.get("title") or "Agentic Determinism Index (ADI)")
    run_stamp = payload.get("run_stamp") or ""
    finished = payload.get("finished") or payload.get("started") or ""
    last_run = _short_dt(finished) or html.escape(run_stamp) or "n/a"
    n_runs = payload.get("n_runs")
    if n_runs is None:
        n_runs = 1 if payload.get("run_dir") else 0
    run_id = payload.get("run_id") or short_stack_id(run_stamp or "none")
    run_id_disp = display_stack_id(run_id)
    run_href = payload.get("run_href") or f"r/{run_id}/"

    rows = []
    for entry in payload.get("leaders", []):
        medal = f'<span class="medal">{html.escape(entry.get("medal") or "")}</span> ' if entry.get("medal") else ""
        display = entry.get("display") or entry.get("label") or entry.get("provider", "")
        model = entry.get("model") or ""
        if not model and entry.get("models"):
            model = ", ".join(m.get("name", "") for m in entry["models"] if m.get("name"))
        exact_rate = entry.get("exact_match_rate")
        byte_cell, row_class = _byte_exact_cell(exact_rate)
        tr_cls = f' class="{row_class}"' if row_class else ""
        sid = entry.get("stack_id") or short_stack_id(
            f"{entry.get('provider')}|{entry.get('model')}|{entry.get('label') or ''}"
        )
        sid_disp = display_stack_id(sid)
        # Link to the run detail page (same relative path on GitHub Pages and mirrors).
        sid_href = entry.get("stack_href") or f"{run_href}#{sid}"
        det = int(entry.get("deterministic_runs") or 0)
        seen = int(entry.get("runs_seen") or 0) or 1
        streak = int(entry.get("streak") or 0)
        survive_title = (
            f"{det} of {seen} scored reference runs fully byte-exact; "
            f"current streak {streak}"
        )
        survive_cell = (
            f'<span title="{html.escape(survive_title, quote=True)}">'
            f"{det}&nbsp;/&nbsp;{seen}</span>"
            f'<div class="sid">streak {streak}</div>'
        )
        rows.append(
            "<tr{tr_cls}>"
            "<td>{rank}</td>"
            "<td>{medal}{display}<div class=\"sid\">"
            "<a href=\"{sid_href}\" title=\"Open run detail for this stack\">"
            "{sid_disp}</a></div></td>"
            "<td>{model}</td>"
            "<td>{score}</td>"
            "<td>{mode_share}</td>"
            "<td>{byte_cell}</td>"
            "<td>{survive}</td>"
            "<td>{distinct}</td>"
            "<td>{cases}</td>"
            "</tr>".format(
                tr_cls=tr_cls,
                rank=entry.get("rank", ""),
                medal=medal,
                display=html.escape(display),
                sid_href=html.escape(sid_href, quote=True),
                sid_disp=html.escape(sid_disp),
                model=html.escape(model) if model else "n/a",
                score=entry.get("score", 0.0),
                mode_share=_format_pct(entry.get("mean_mode_share")),
                byte_cell=byte_cell,
                survive=survive_cell,
                distinct=_format_float(entry.get("mean_distinct")),
                cases=entry.get("rows", 0),
            )
        )

    rows_html = "\n".join(rows) if rows else (
        '<tr><td colspan="9">No scored reference run found.</td></tr>'
    )

    # Use top-level counts (always freshly computed in build_payload) with fallbacks.
    total_providers = payload.get("providers") or (payload.get("summary") or {}).get("providers", 0)
    total_models = payload.get("models") or (payload.get("summary") or {}).get("models", 0)
    total_cases = payload.get("cases") or (payload.get("summary") or {}).get("cases", 0)
    scored_tuples = payload.get("scored_tuples") or len(payload.get("leaders") or [])

    # Final safety: derive from leaders so numbers are always live with the payload data.
    if not total_providers or not total_models:
        pset = {e.get("provider") for e in (payload.get("leaders") or []) if e.get("provider")}
        mset = {e.get("model") for e in (payload.get("leaders") or []) if e.get("model")}
        total_providers = total_providers or len(pset)
        total_models = total_models or len(mset)
    if not total_cases:
        try:
            total_cases = max((int(e.get("rows") or 0) for e in (payload.get("leaders") or [])), default=0) or total_cases
        except Exception:
            pass
    if scored_tuples in (None, 0):
        scored_tuples = len(payload.get("leaders") or [])

    stack_drift_rows = []
    for item in payload.get("stack_drift", []):
        timeline_parts = []
        for point in item.get("runs", []):
            fp = ", ".join(point.get("fingerprints", [])) or "n/a"
            mv = ", ".join(point.get("model_versions", [])) or "n/a"
            timeline_parts.append(
                "{stamp}: [{fp}] / [{mv}]".format(
                    stamp=html.escape(point.get("run_stamp", "")),
                    fp=html.escape(fp),
                    mv=html.escape(mv),
                )
            )
        timeline = " → ".join(timeline_parts) if timeline_parts else "n/a"
        stack_drift_rows.append(
            "<tr>"
            "<td>{provider}</td>"
            "<td>{model}</td>"
            "<td>{drift}</td>"
            "<td class=\"timeline\">{timeline}</td>"
            "</tr>".format(
                provider=html.escape(item.get("provider", "")),
                model=html.escape(item.get("model", "")),
                drift=item.get("drift_count", 0),
                timeline=timeline,
            )
        )

    if stack_drift_rows:
        drift_block = (
            '<table class="drift"><thead><tr>'
            "<th>Provider</th><th>Model</th><th>Drift events</th><th>Timeline</th>"
            "</tr></thead><tbody>\n"
            + "\n".join(stack_drift_rows)
            + "\n</tbody></table>"
        )
    else:
        drift_block = (
            '<p class="meta">No multi-run stack-ID history yet. '
            "Drift appears after two or more scored reference runs.</p>"
        )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      body {{
        font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
        margin: 2rem auto;
        max-width: 1100px;
        color: #0f172a;
        background: #f8fafc;
        padding: 0 1rem 3rem;
      }}
      h1 {{ margin-bottom: 0.25rem; }}
      h2 {{ margin-top: 2.25rem; }}
      .lead {{ color: #334155; margin: 0.25rem 0 1rem; }}
      .summary {{
        display: flex; flex-wrap: wrap; gap: 0.75rem 1.25rem;
        color: #475569; font-size: 0.95rem; margin-bottom: 1.25rem;
      }}
      .summary strong {{ color: #0f172a; font-weight: 600; }}
      .stats {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 0.5rem;
        margin: 0 0 1.5rem;
      }}
      .stat {{
        background: #fff; border: 1px solid #e2e8f0; border-radius: 0.5rem; padding: 0.65rem 0.75rem;
      }}
      .stat .value {{ font-size: 1.35rem; font-weight: 700; }}
      .stat .label {{ color: #64748b; font-size: 0.8rem; margin-top: 0.15rem; }}
      table {{ width: 100%; border-collapse: collapse; background: #fff; }}
      th, td {{ border: 1px solid #e2e8f0; padding: 0.55rem 0.65rem; text-align: left; vertical-align: top; }}
      th {{ background: #f1f5f9; font-size: 0.85rem; }}
      tr.row-exact {{ background: #ecfdf5; }}
      tr.row-exact td {{ border-color: #a7f3d0; }}
      .medal {{ margin-right: 0.15rem; }}
      .meta {{ color: #64748b; font-size: 0.9rem; margin: 1rem 0; }}
      .pill {{
        display: inline-block; border-radius: 9999px; padding: 0.15rem 0.55rem;
        font-size: 0.8rem; font-weight: 600; white-space: nowrap;
      }}
      .pill-yes {{ background: #d1fae5; color: #065f46; }}
      .pill-partial {{ background: #fef3c7; color: #92400e; }}
      .pill-no {{ background: #fee2e2; color: #991b1b; }}
      .pill-na {{ background: #e2e8f0; color: #475569; }}
      .timeline {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 0.8rem; white-space: nowrap; overflow-x: auto; max-width: 28rem;
      }}
      .sid {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 0.75rem; color: #64748b; margin-top: 0.2rem;
      }}
      .sid a {{ color: #64748b; text-decoration: none; border-bottom: 1px dotted #94a3b8; }}
      .sid a:hover {{ color: #1d4ed8; }}
      a {{ color: #1d4ed8; }}
    </style>
  </head>
  <body>
    <h1>{title}</h1>
    <p class="lead">Reference leaderboard by serving tuple. Top three earn medals for the latest snapshot.</p>
    <div class="summary">
      <span>Last run: <strong>{html.escape(last_run)}</strong></span>
      <span>Reference runs: <strong>{int(n_runs)}</strong></span>
      <span>Run: <strong><a href="{html.escape(run_href, quote=True)}" title="Run detail page">r/{html.escape(run_id)}/</a></strong></span>
    </div>
    <div class="stats">
      <div class="stat"><div class="value">{total_providers}</div><div class="label">providers</div></div>
      <div class="stat"><div class="value">{total_models}</div><div class="label">models</div></div>
      <div class="stat"><div class="value">{total_cases}</div><div class="label">cases</div></div>
      <div class="stat"><div class="value">{scored_tuples}</div><div class="label">scored tuples</div></div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Rank</th>
          <th>Serving tuple</th>
          <th>Model</th>
          <th>Score</th>
          <th>Mode share</th>
          <th>Byte-exact replay</th>
          <th>Deterministic runs</th>
          <th>Mean distinct</th>
          <th>Cases</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
    <p class="meta">
      <strong>Byte-exact replay</strong> is the property that matters for audit trails:
      green rows returned identical bytes on every successful repeat of the same request.
      <strong>Deterministic runs</strong> counts how many scored reference runs that serving
      tuple stayed fully byte-exact (N of M), plus the current consecutive streak.
      Mode share is the fraction matching the most common completion (can be high without bit-identity).
      All-error probes are omitted. Scores recompute from raw transcripts; community replications are not merged.
    </p>
    <h2>Stack-drift timeline</h2>
    <p class="meta">When a provider changes <code>system_fingerprint</code> / model version across reference runs.</p>
    {drift_block}
    <p class="meta" style="margin-top: 1.75rem; font-size: 0.8rem;">
      Maintained by <a href="https://lemma.ventures">Lemma Ventures AG</a>.
      Source: <a href="https://github.com/lemma-ventures/agentic-determinism-index">lemma-ventures/agentic-determinism-index</a> (MIT).
    </p>
  </body>
</html>
"""


def build_payload(run_dir=None, run_root=None, watch_dir=None):
    """Build page payload from a scored run and optional watch history.

    ``run_dir`` may be None when only stack-watch data exists; the leaderboard
    table then shows an empty state while the drift panel can still render.
    """
    scores = load_scores(run_dir) if run_dir else []
    manifest = load_manifest(run_dir) if run_dir else {}
    leaders = aggregate_leaderboard(scores) if scores else []
    root = run_root or (os.path.dirname(run_dir) if run_dir else None)
    n_runs = len(_list_scored_runs(root)) if root else (1 if run_dir else 0)
    if root:
        apply_survival(leaders, tuple_deterministic_survival(root))

    if run_dir:
        first_metrics = build_first_metrics(run_dir, run_root)
    else:
        first_metrics = {
            "summary": {
                "providers": 0,
                "models": 0,
                "cases": 0,
                "probe_rows": 0,
                "scored_rows": 0,
                "requests": 0,
                "non_error_requests": 0,
                "errors": 0,
                "success_rate": None,
            },
            "stack_drift": build_stack_drift(run_root) if run_root else [],
        }

    # Headline stats are *always* derived from the data for this run at build time.
    prov = mod = cas = 0
    if scores:
        s = _summarize_run_rows(scores)
        prov = s.get("providers", 0)
        mod = s.get("models", 0)
        cas = s.get("cases", 0)
    scored_t = len(leaders or [])

    if watch_dir:
        try:
            from .watch import build_watch_drift, load_watch_history
            hist = load_watch_history(os.path.join(watch_dir, "history.jsonl"))
            watch_drift = build_watch_drift(hist)
            if watch_drift:
                first_metrics = dict(first_metrics)
                first_metrics["watch_drift"] = watch_drift
        except Exception:
            pass

    run_stamp = os.path.basename(os.path.normpath(run_dir)) if run_dir else ""
    run_id = short_stack_id(run_stamp or "none")
    for entry in leaders:
        sid = short_stack_id(
            f"{entry.get('provider')}|{entry.get('model')}|{entry.get('label') or ''}|{run_stamp}"
        )
        entry["stack_id"] = sid
        entry["stack_href"] = f"r/{run_id}/#{sid}"

    return {
        "title": "Agentic Determinism Index (ADI)",
        "run_dir": run_dir or "",
        "run_stamp": run_stamp,
        "run_id": run_id,
        "run_href": f"r/{run_id}/",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "started": manifest.get("started", ""),
        "finished": manifest.get("finished", ""),
        "n_runs": n_runs,
        "leaders": leaders,
        # Explicit fresh counts so the 4 headline stats are always up-to-date with this run.
        "providers": prov,
        "models": mod,
        "cases": cas,
        "scored_tuples": scored_t,
        **first_metrics,
    }


def render_run_page(payload, scores):
    """Detail page for one reference run, addressable by short stack id."""
    title = html.escape(payload.get("title") or "Agentic Determinism Index (ADI)")
    run_id = payload.get("run_id") or short_stack_id(payload.get("run_stamp") or "none")
    run_disp = display_stack_id(run_id)
    stamp = html.escape(payload.get("run_stamp") or "")
    finished = _short_dt(payload.get("finished") or payload.get("started") or "")
    rows = []
    for row in scores or []:
        sid = short_stack_id(
            f"{row.get('provider')}|{row.get('model')}|{row.get('label') or ''}|{payload.get('run_stamp') or ''}"
        )
        bi = row.get("byte_identical")
        if bi is True:
            bi_html = '<span class="pill pill-yes">Yes · byte-exact</span>'
        elif bi is False:
            bi_html = '<span class="pill pill-no">No</span>'
        else:
            bi_html = '<span class="pill pill-na">n/a</span>'
        rows.append(
            f'<tr id="{html.escape(sid, quote=True)}">'
            f'<td class="sid">{html.escape(display_stack_id(sid))}</td>'
            f'<td>{html.escape(str(row.get("provider") or ""))}</td>'
            f'<td>{html.escape(str(row.get("model") or ""))}</td>'
            f'<td>{html.escape(str(row.get("label") or row.get("case") or ""))}</td>'
            f'<td>{row.get("n_ok", 0)}/{row.get("n", 0)}</td>'
            f'<td>{_format_pct(row.get("mode_share"))}</td>'
            f'<td>{bi_html}</td>'
            f'<td>{row.get("distinct", "n/a")}</td>'
            f"</tr>"
        )
    body_rows = "\n".join(rows) or '<tr><td colspan="8">No probes.</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Run {html.escape(run_disp)} · {title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 1100px;
      color: #0f172a; background: #f8fafc; padding: 0 1rem 3rem; }}
    a {{ color: #1d4ed8; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 0.5rem 0.65rem; text-align: left; }}
    th {{ background: #f1f5f9; font-size: 0.85rem; }}
    .sid {{ font-family: ui-monospace, monospace; font-size: 0.8rem; color: #64748b; }}
    .pill {{ display: inline-block; border-radius: 9999px; padding: 0.15rem 0.55rem;
      font-size: 0.8rem; font-weight: 600; }}
    .pill-yes {{ background: #d1fae5; color: #065f46; }}
    .pill-no {{ background: #fee2e2; color: #991b1b; }}
    .pill-na {{ background: #e2e8f0; color: #475569; }}
    tr:target {{ background: #ecfdf5; outline: 2px solid #34d399; }}
    .meta {{ color: #64748b; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <p class="meta"><a href="../../index.html">← {title}</a></p>
  <h1>Run {html.escape(run_disp)}</h1>
  <p class="meta">Full id <code>{html.escape(run_id)}</code> · stamp <code>{stamp}</code>
    · finished <strong>{html.escape(finished or "n/a")}</strong></p>
  <table>
    <thead><tr>
      <th>Stack id</th><th>Provider</th><th>Model</th><th>Case / pin</th>
      <th>n_ok</th><th>Mode share</th><th>Byte-exact</th><th>Distinct</th>
    </tr></thead>
    <tbody>
      {body_rows}
    </tbody>
  </table>
  <p class="meta" style="margin-top:1.5rem;font-size:0.8rem;">
    Maintained by <a href="https://lemma.ventures">Lemma Ventures AG</a>.
    Transcripts live under <code>runs/reference/{stamp}/</code> in the
    <a href="https://github.com/lemma-ventures/agentic-determinism-index">source repo</a>.
  </p>
</body>
</html>
"""


def write_site(out_html, run_dir=None, run_root=None, watch_dir=None):
    """Write leaderboard + per-run detail pages. Returns list of paths written."""
    payload = build_payload(run_dir, run_root=run_root, watch_dir=watch_dir)
    out_dir = os.path.dirname(out_html) or "."
    os.makedirs(out_dir, exist_ok=True)
    written = []
    with open(out_html, "w") as f:
        f.write(render_html(payload))
    written.append(out_html)

    if run_dir and os.path.isdir(run_dir):
        scores = load_scores(run_dir)
        run_id = payload.get("run_id") or short_stack_id(payload.get("run_stamp") or "none")
        run_page_dir = os.path.join(out_dir, "r", run_id)
        os.makedirs(run_page_dir, exist_ok=True)
        run_page = os.path.join(run_page_dir, "index.html")
        with open(run_page, "w") as f:
            f.write(render_run_page(payload, scores))
        written.append(run_page)
        # Also copy scores.json next to the page for transparency
        try:
            import shutil
            shutil.copy2(
                os.path.join(run_dir, "scores.json"),
                os.path.join(run_page_dir, "scores.json"),
            )
            written.append(os.path.join(run_page_dir, "scores.json"))
        except OSError:
            pass
    return written
