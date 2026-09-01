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


def render_html(payload):
    generated = payload.get("generated_at") or datetime.datetime.utcnow().isoformat()
    title = html.escape(payload.get("title") or "Determinism Index")
    run_dir = html.escape(payload.get("run_dir") or "")
    run_stamp = html.escape(payload.get("run_stamp") or "")
    started = html.escape(payload.get("started") or "")
    finished = html.escape(payload.get("finished") or "")

    rows = []
    for entry in payload.get("leaders", []):
        medal = f" <span class=\"medal\">{entry.get('medal','')}</span>" if entry.get("medal") else ""
        display = entry.get("display") or entry.get("label") or entry.get("provider", "")
        model = entry.get("model") or ""
        if not model and entry.get("models"):
            model = ", ".join(m.get("name", "") for m in entry["models"] if m.get("name"))
        rows.append("""
            <tr>
              <td>{rank}</td>
              <td>{medal_html} {display}</td>
              <td>{score}</td>
              <td>{mode_share}</td>
              <td>{exact}</td>
              <td>{distinct}</td>
              <td>{model}</td>
              <td>{cases}</td>
            </tr>
        """.format(
            rank=entry.get("rank", ""),
            medal_html=medal,
            display=html.escape(display),
            score=entry.get("score", 0.0),
            mode_share=_format_float(entry.get("mean_mode_share")),
            exact=_format_float(entry.get("exact_match_rate")),
            distinct=_format_float(entry.get("mean_distinct")),
            model=html.escape(model) if model else "n/a",
            cases=entry.get("rows", 0),
        ).strip())

    rows_html = "\n".join(rows) if rows else """<tr><td colspan=8>No scored reference run found.</td></tr>"""

    summary = payload.get("summary", {}) or {}
    total_models = summary.get("models", 0)
    total_providers = summary.get("providers", 0)
    total_cases = summary.get("cases", 0)
    total_requests = summary.get("requests", 0)
    success_rate = summary.get("success_rate")
    success_text = f"{success_rate:.1%}" if success_rate is not None else "n/a"

    stack_drift_rows = []
    for item in payload.get("stack_drift", []):
        timeline_parts = []
        for point in item.get("runs", []):
            fp = ", ".join(point.get("fingerprints", [])) or "n/a"
            mv = ", ".join(point.get("model_versions", [])) or "n/a"
            timeline_parts.append("{stamp}: [{fp}] / [{mv}]".format(
                stamp=html.escape(point.get("run_stamp", "")),
                fp=html.escape(fp),
                mv=html.escape(mv),
            ))
        timeline = " → ".join(timeline_parts) if timeline_parts else "n/a"
        latest_fp = ", ".join(item.get("latest_fingerprints", [])) or "n/a"
        latest_mv = ", ".join(item.get("latest_model_versions", [])) or "n/a"
        stack_drift_rows.append(
            """
            <tr>
              <td>{provider}</td>
              <td>{model}</td>
              <td>{drift}</td>
              <td>{timeline}</td>
              <td>{latest_fingerprints}</td>
              <td>{latest_model_versions}</td>
            </tr>
            """.format(
                provider=html.escape(item.get("provider", "")),
                model=html.escape(item.get("model", "")),
                drift=item.get("drift_count", 0),
                timeline=timeline,
                latest_fingerprints=html.escape(latest_fp),
                latest_model_versions=html.escape(latest_mv),
            ).strip()
        )

    stack_rows_html = "\n".join(stack_drift_rows)
    has_drift = bool(stack_rows_html)
    if has_drift:
        drift_block = (
            "<table class=\"drift\">\n"
            "<thead><tr>"
            "<th>Provider</th>"
            "<th>Model</th>"
            "<th>Drift events</th>"
            "<th>Timeline</th>"
            "<th>Latest fingerprints</th>"
            "<th>Latest model versions</th>"
            "</tr></thead>\n"
            "<tbody>\n"
            f"{stack_rows_html}\n"
            "</tbody></table>"
        )
    else:
        drift_block = (
            "<table class=\"drift\">\n"
            "<thead><tr><th>Provider</th><th>Model</th><th>Drift events</th>"
            "<th>Timeline</th><th>Latest fingerprints</th><th>Latest model versions</th></tr></thead>\n"
            "<tbody><tr><td colspan=6>Stack IDs not yet available for this provider set.</td></tr></tbody></table>"
        )

    return """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
      <style>
        body {{
          font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
          margin: 2rem;
          color: #0f172a;
          background: #f8fafc;
        }}
        h1 {{ margin-bottom: 0.2rem; }}
        h2 {{ margin-top: 2rem; }}
        .lead {{ color: #334155; margin-top: 0.2rem; }}
        .stats {{
          display: grid;
          grid-template-columns: repeat(5, minmax(0, 1fr));
          gap: 0.5rem;
          margin: 1rem 0 1.5rem;
        }}
        .stat {{
          background: #fff;
          border: 1px solid #e2e8f0;
          border-radius: 0.5rem;
          padding: 0.6rem;
        }}
        .stat .value {{
          font-size: 1.3rem;
          font-weight: 700;
          color: #0f172a;
        }}
        .stat .label {{
          color: #475569;
          font-size: 0.85rem;
          margin-top: 0.2rem;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          margin-top: 1rem;
          background: #fff;
        }}
      th, td {{
        border: 1px solid #e2e8f0;
        padding: 0.6rem;
        text-align: left;
        vertical-align: top;
      }}
      th {{ background: #f1f5f9; }}
      .medal {{ font-size: 1.1rem; margin-right: 0.2rem; }}
      .meta {{ color: #475569; font-size: 0.9rem; margin-bottom: 1rem; }}
        .badge {{
          display: inline-block;
          background: #e2e8f0;
          border-radius: 9999px;
          padding: 0.1rem 0.6rem;
          font-size: 0.85rem;
          color: #0f172a;
        }}
        .timeline {{
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
          white-space: nowrap;
          overflow-x: auto;
        }}
      </style>
  </head>
  <body>
    <h1>{title}</h1>
    <div class="lead">Reference results by serving tuple, with top-3 medals.</div>
    <div class="meta">
      source: <span class="badge">{run_dir}</span>
      • run: <span class="badge">{run_stamp}</span>
      • generated: <span class="badge">{generated}</span>
      • started: <span class="badge">{started}</span>
      • finished: <span class="badge">{finished}</span>
    </div>
    <div class="stats">
      <div class="stat"><div class="value">{total_models}</div><div class="label">models</div></div>
      <div class="stat"><div class="value">{total_providers}</div><div class="label">providers</div></div>
      <div class="stat"><div class="value">{total_cases}</div><div class="label">cases</div></div>
      <div class="stat"><div class="value">{total_requests}</div><div class="label">raw responses</div></div>
      <div class="stat"><div class="value">{success_text}</div><div class="label">successful request rate</div></div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Rank</th>
          <th>Serving tuple</th>
          <th>Score</th>
          <th>Mean mode_share</th>
          <th>Byte-identical rate</th>
          <th>Mean distinct</th>
          <th>Model</th>
          <th>Cases</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
    <p class="meta" style="margin-top: 1rem;">
      Notes: each row is one serving tuple (provider, model, optional pin).
      mode_share and byte-identical are per case, then averaged across scored cases only.
      All-error probes (EOL models, missing endpoints) are omitted, not shown as zeros.
      Scores are recomputed from raw transcripts and do not merge community replications.
    </p>
    <h2>Stack-drift timeline</h2>
    <p class="meta">For each (provider, model) tuple, this shows the set of observed stack IDs by run.</p>
    {drift_block}
    <p class="meta" style="margin-top: 1.5rem; font-size:0.8rem;">
      Maintained by <a href="https://lemma.ventures">Lemma Ventures AG</a>.
      Source: <a href="https://github.com/lemma-ventures/agentic-determinism-index">lemma-ventures/agentic-determinism-index</a> (MIT).
    </p>
  </body>
</html>
""".format(
        title=title,
        rows=rows_html,
        run_dir=run_dir,
        run_stamp=html.escape(run_stamp),
        generated=html.escape(str(generated)),
        started=started,
        finished=finished,
        total_models=total_models,
        total_providers=total_providers,
        total_cases=total_cases,
        total_requests=total_requests,
        success_text=success_text,
        drift_block=drift_block,
    )


def build_payload(run_dir=None, run_root=None, watch_dir=None):
    """Build page payload from a scored run and optional watch history.

    ``run_dir`` may be None when only stack-watch data exists; the leaderboard
    table then shows an empty state while the drift panel can still render.
    """
    scores = load_scores(run_dir) if run_dir else []
    manifest = load_manifest(run_dir) if run_dir else {}
    leaders = aggregate_leaderboard(scores) if scores else []
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

    # Merge continuous stack-watch history when present.
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
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "started": manifest.get("started", ""),
        "finished": manifest.get("finished", ""),
        "leaders": leaders,
        **first_metrics,
    }
