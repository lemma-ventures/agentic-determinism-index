"""Generate a static website for published Determinism Index results."""

import datetime
import html
import json
import os


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


def _as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def aggregate_leaderboard(rows):
    providers = {}
    for row in rows:
        provider = row.get("provider")
        if not provider:
            continue
        model = row.get("model") or "unknown"
        stats = providers.setdefault(provider, {
            "provider": provider,
            "rows": 0,
            "mode_sum": 0.0,
            "mode_rows": 0,
            "exact_sum": 0,
            "exact_rows": 0,
            "distinct_sum": 0.0,
            "distinct_rows": 0,
            "models": {},
        })

        stats["rows"] += 1
        model_stats = stats["models"].setdefault(model, {
            "rows": 0,
            "mode_sum": 0.0,
            "mode_rows": 0,
            "exact_sum": 0,
            "exact_rows": 0,
            "distinct_sum": 0.0,
            "distinct_rows": 0,
        })
        model_stats["rows"] += 1

        mode_share = _as_float(row.get("mode_share"))
        if mode_share is not None:
            stats["mode_sum"] += mode_share
            stats["mode_rows"] += 1
            model_stats["mode_sum"] += mode_share
            model_stats["mode_rows"] += 1

        distinct = _as_float(row.get("distinct"))
        if distinct is not None:
            stats["distinct_sum"] += distinct
            stats["distinct_rows"] += 1
            model_stats["distinct_sum"] += distinct
            model_stats["distinct_rows"] += 1

        byte_identical = row.get("byte_identical")
        if mode_share is not None:
            stats["exact_rows"] += 1
            model_stats["exact_rows"] += 1
            if byte_identical:
                stats["exact_sum"] += 1
                model_stats["exact_sum"] += 1

    ranked = []
    for p, s in providers.items():
        mode_rows = s["mode_rows"]
        exact_rows = s["exact_rows"]
        distinct_rows = s["distinct_rows"]
        mean_mode = s["mode_sum"] / mode_rows if mode_rows else 0.0
        exact_rate = s["exact_sum"] / exact_rows if exact_rows else 0.0
        mean_distinct = s["distinct_sum"] / distinct_rows if distinct_rows else None
        if mean_distinct is None:
            stability = 0.0
        else:
            stability = 1.0 / (1.0 + max(0.0, mean_distinct - 1.0))
        score = (0.70 * mean_mode) + (0.25 * exact_rate) + (0.05 * stability)
        score *= 100

        models = []
        for name, m in s["models"].items():
            m_mode_rows = m["mode_rows"]
            m_exact_rows = m["exact_rows"]
            if m_mode_rows == 0:
                continue
            models.append({
                "name": name,
                "rows": m["rows"],
                "mean_mode_share": round(m["mode_sum"] / m_mode_rows, 4),
                "exact_match": round(m["exact_sum"] / m_exact_rows, 4)
                if m_exact_rows else None,
            })

        ranked.append({
            "provider": p,
            "rows": s["rows"],
            "mean_mode_share": round(mean_mode, 4),
            "exact_match_rate": round(exact_rate, 4),
            "mean_distinct": round(mean_distinct, 4) if mean_distinct is not None else None,
            "score": round(score, 2),
            "models": models,
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
        model_count = len(entry.get("models", []))
        models = ", ".join(
            f"{m['name']} ({m['rows']} cases)"
            for m in sorted(entry.get("models", []), key=lambda m: m["name"])
        )
        rows.append("""
            <tr>
              <td>{rank}</td>
              <td>{medal_html} {provider}</td>
              <td>{score}</td>
              <td>{mode_share}</td>
              <td>{exact}</td>
              <td>{distinct}</td>
              <td>{model_count}</td>
              <td>{models}</td>
              <td>{cases}</td>
            </tr>
        """.format(
            rank=entry.get("rank", ""),
            medal_html=medal,
            provider=html.escape(entry.get("provider", "")),
            score=entry.get("score", 0.0),
            mode_share=_format_float(entry.get("mean_mode_share")),
            exact=_format_float(entry.get("exact_match_rate")),
            distinct=_format_float(entry.get("mean_distinct")),
            model_count=model_count,
            models=html.escape(models) if models else "n/a",
            cases=entry.get("rows", 0),
        ).strip())

    rows_html = "\n".join(rows) if rows else """<tr><td colspan=8>No scored reference run found.</td></tr>"""

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
      .lead {{ color: #334155; margin-top: 0.2rem; }}
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
    </style>
  </head>
  <body>
    <h1>{title}</h1>
    <div class="lead">Reference results by provider with top3 medals.</div>
    <div class="meta">
      source: <span class="badge">{run_dir}</span>
      • run: <span class="badge">{run_stamp}</span>
      • generated: <span class="badge">{generated}</span>
      • started: <span class="badge">{started}</span>
      • finished: <span class="badge">{finished}</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>Rank</th>
          <th>Provider</th>
          <th>Score</th>
          <th>Mean mode_share</th>
          <th>Byte-identical rate</th>
          <th>Mean distinct</th>
          <th>Models</th>
          <th>Cases</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
    <p class="meta" style="margin-top: 1rem;">
      Notes: mode_share and byte-identical are per (provider, model, case), then averaged.
      Scores are recomputed from raw transcripts before publish and do not merge community replications.
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
    )


def build_payload(run_dir):
    scores = load_scores(run_dir)
    manifest = load_manifest(run_dir)
    leaders = aggregate_leaderboard(scores)
    return {
        "title": "Determinism Index",
        "run_dir": run_dir,
        "run_stamp": os.path.basename(run_dir),
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "started": manifest.get("started", ""),
        "finished": manifest.get("finished", ""),
        "leaders": leaders,
    }
