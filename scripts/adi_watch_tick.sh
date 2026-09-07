#!/usr/bin/env bash
# Installed to /usr/local/bin/adi-watch-tick on the lemma-web host.
# Source of truth in-repo; refresh via setup_watch_on_lemma_host.sh or
# website workflow install-adi-watch-tick.yml on lemma-web.
set -euo pipefail

WATCH_DIR=/opt/adi-watch
ENV_FILE=/etc/adi-watch.env

if [ ! -f "$ENV_FILE" ]; then
  echo "missing $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

export OPENROUTER_API_KEY
export NVIDIA_API_KEY
# Optional: EigenAI (bit-exact claim); target is skipped if unset
export EIGENAI_API_KEY=${EIGENAI_API_KEY:-}

cd "$WATCH_DIR"

echo "==> git pull"
git fetch origin main
git checkout main
git pull --ff-only || true

echo "==> run watch tick"
export WATCH_DIR=runs/watch
export RUN_ROOT=runs/reference
mkdir -p "$WATCH_DIR" "$RUN_ROOT"

set +e
./scripts/ci_watch.sh
WATCH_RC=$?
set -e
if [ "$WATCH_RC" -ne 0 ] && [ "$WATCH_RC" -ne 2 ]; then
  exit "$WATCH_RC"
fi

echo "==> commit & push (watch_rc=$WATCH_RC; site gated)"
./scripts/host_commit_push.sh

echo "adi-watch tick done"
