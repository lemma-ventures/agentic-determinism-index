"""Generate a static website for published Determinism Index results."""

import datetime
import html
import json
import os
from collections import defaultdict


MEDALS = {1: "1st", 2: "2nd", 3: "3rd"}


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
    title = html.escape(payload.get("title") or "Determinism Index")
    run_stamp = payload.get("run_stamp") or ""
    finished = payload.get("finished") or payload.get("started") or ""
    last_run = _short_dt(finished) or html.escape(run_stamp) or "n/a"
    n_runs = payload.get("n_runs")
    if n_runs is None:
        n_runs = 1 if payload.get("run_dir") else 0

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
        rows.append(
            "<tr{tr_cls}>"
            "<td>{rank}</td>"
            "<td>{medal}{display}</td>"
            "<td>{model}</td>"
            "<td>{score}</td>"
            "<td>{mode_share}</td>"
            "<td>{byte_cell}</td>"
            "<td>{distinct}</td>"
            "<td>{cases}</td>"
            "</tr>".format(
                tr_cls=tr_cls,
                rank=entry.get("rank", ""),
                medal=medal,
                display=html.escape(display),
                model=html.escape(model) if model else "n/a",
                score=entry.get("score", 0.0),
                mode_share=_format_pct(entry.get("mean_mode_share")),
                byte_cell=byte_cell,
                distinct=_format_float(entry.get("mean_distinct")),
                cases=entry.get("rows", 0),
            )
        )

    rows_html = "\n".join(rows) if rows else (
        '<tr><td colspan="8">No scored reference run found.</td></tr>'
    )

    summary = payload.get("summary", {}) or {}
    total_models = summary.get("models", 0)
    total_providers = summary.get("providers", 0)
    total_cases = summary.get("cases", 0)

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
      a {{ color: #1d4ed8; }}
    </style>
  </head>
  <body>
    <h1>{title}</h1>
    <p class="lead">Reference leaderboard by serving tuple. Top three earn medals for the latest snapshot.</p>
    <div class="summary">
      <span>Last run: <strong>{html.escape(last_run)}</strong></span>
      <span>Reference runs: <strong>{int(n_runs)}</strong></span>
    </div>
    <div class="stats">
      <div class="stat"><div class="value">{total_providers}</div><div class="label">providers</div></div>
      <div class="stat"><div class="value">{total_models}</div><div class="label">models</div></div>
      <div class="stat"><div class="value">{total_cases}</div><div class="label">cases</div></div>
      <div class="stat"><div class="value">{len(payload.get("leaders") or [])}</div><div class="label">scored tuples</div></div>
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

    return {
        "title": "Determinism Index",
        "run_dir": run_dir or "",
        "run_stamp": os.path.basename(run_dir) if run_dir else "",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "started": manifest.get("started", ""),
        "finished": manifest.get("finished", ""),
        "n_runs": n_runs,
        "leaders": leaders,
        **first_metrics,
    }
