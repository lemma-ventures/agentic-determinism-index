#!/usr/bin/env bash
# Hourly CI tick: cheap stack-ID watch + selective full score for due targets.
# Persists runs/watch/ state so adaptive backoff survives across runners.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export WATCH_DIR="${WATCH_DIR:-runs/watch}"
export RUN_ROOT="${RUN_ROOT:-runs/reference}"
WATCH_CONFIG="${WATCH_CONFIG:-configs/watch.json}"
SCORE_CONFIG="${SCORE_CONFIG:-configs/continuous.json}"
CASES="${CASES:-cases/default/cases.json}"
WATCH_CASES="${WATCH_CASES:-cases/watch/cases.json}"
SITE_OUT="${SITE_OUT:-website/index.html}"

mkdir -p "$WATCH_DIR" "$RUN_ROOT"

python3 - <<'PY'
"""Seed watch score hints from the latest scored reference run if empty."""
import os
from agentic_determinism_index.site import latest_scored_run, load_scores
from agentic_determinism_index.watch import ingest_score_hints, load_watch_state

watch_dir = os.environ.get("WATCH_DIR", "runs/watch")
run_root = os.environ.get("RUN_ROOT", "runs/reference")
state = load_watch_state(watch_dir)
targets = state.get("targets") or {}
needs_seed = not targets or all(
    t.get("last_score_epoch") is None for t in targets.values()
)
if not needs_seed:
    print("watch state already has score hints")
    raise SystemExit(0)
latest = latest_scored_run(run_root)
if not latest:
    print("no scored reference run to seed from")
    raise SystemExit(0)
rows = load_scores(latest)
ingest_score_hints(watch_dir, rows, run_stamp=os.path.basename(latest))
print(f"seeded watch hints from {latest} ({len(rows)} score rows)")
PY

echo "==> watch tick"
set +e
python3 -m agentic_determinism_index watch \
  --config "$WATCH_CONFIG" \
  --cases "$WATCH_CASES" \
  --out "$WATCH_DIR"
WATCH_RC=$?
set -e
# exit 2 = drift detected; still continue
if [ "$WATCH_RC" -ne 0 ] && [ "$WATCH_RC" -ne 2 ]; then
  exit "$WATCH_RC"
fi

echo "==> selective full score (--due-only)"
RUN_OUT="$(
  python3 -m agentic_determinism_index run \
    --config "$SCORE_CONFIG" \
    --cases "$CASES" \
    --out "$RUN_ROOT" \
    --watch-dir "$WATCH_DIR" \
    --due-only \
    --burst "${BURST:-8}" \
    --serial "${SERIAL:-2}" \
    --gap "${GAP:-10}" \
    | tee /tmp/adi-run.out | tail -n 1
)"

if [ -n "${RUN_OUT:-}" ] && [ -d "$RUN_OUT" ]; then
  echo "==> score $RUN_OUT"
  python3 -m agentic_determinism_index score "$RUN_OUT" --watch-dir "$WATCH_DIR"
  echo "==> rebuild site"
  python3 -m agentic_determinism_index site \
    --run-root "$RUN_ROOT" \
    --watch-dir "$WATCH_DIR" \
    --out "$SITE_OUT"
  mkdir -p docs
  rsync -a --delete website/ docs/
else
  echo "no full score this hour; rebuilding site from existing runs"
  python3 -m agentic_determinism_index site \
    --run-root "$RUN_ROOT" \
    --watch-dir "$WATCH_DIR" \
    --out "$SITE_OUT"
  mkdir -p docs
  rsync -a --delete website/ docs/
fi

echo "ci_watch done (watch_rc=$WATCH_RC)"
