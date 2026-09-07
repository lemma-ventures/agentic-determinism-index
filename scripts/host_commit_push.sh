#!/usr/bin/env bash
# Private-host git publish after ci_watch.sh.
#
# Cost control: GitHub Pages (build_type=workflow) only runs when docs/** or
# website/** change. Hourly watch state goes to runs/ only. Site HTML is
# published when:
#   - ci_watch wrote runs/watch/SITE_PUBLISH (full score and/or drift), or
#   - ADI_FORCE_SITE=1, or
#   - last published site is older than ADI_SITE_MAX_AGE_HOURS (default 24)
#
# That cuts ubuntu-latest Pages deploys from ~hourly to ~daily (or on events).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WATCH_STATE_DIR="${WATCH_STATE_DIR:-runs/watch}"
MARKER="${WATCH_STATE_DIR}/SITE_PUBLISH"
MAX_AGE_HOURS="${ADI_SITE_MAX_AGE_HOURS:-24}"
FORCE_SITE="${ADI_FORCE_SITE:-0}"

publish_site=0
reason=""

if [ "$FORCE_SITE" = "1" ]; then
  publish_site=1
  reason="forced"
elif [ -f "$MARKER" ]; then
  publish_site=1
  reason="$(tr '\n' ' ' <"$MARKER" | sed 's/[[:space:]]*$//')"
  reason="${reason:-marker}"
else
  # Stale public leaderboard / "Last watch tick" refresh
  last_site=""
  if [ -f website/index.html ]; then
    last_site=$(git log -1 --format=%ct -- website/index.html 2>/dev/null || true)
  fi
  if [ -z "$last_site" ]; then
    publish_site=1
    reason="no-prior-site"
  else
    now=$(date -u +%s)
    age_h=$(( (now - last_site) / 3600 ))
    if [ "$age_h" -ge "$MAX_AGE_HOURS" ]; then
      publish_site=1
      reason="max-age-${age_h}h"
    fi
  fi
fi

git config user.name "lemma-web watch"
git config user.email "watch@lemma.ventures"

# Never commit the ephemeral publish marker.
rm -f "$MARKER"

if [ "$publish_site" = "1" ]; then
  echo "==> publishing site ($reason)"
  # Ensure docs mirror exists even if ci_watch was interrupted mid-rsync
  if [ -d website ] && [ -f website/index.html ]; then
    mkdir -p docs
    rsync -a --delete website/ docs/
  fi
else
  echo "==> site publish skipped (watch-only; max age ${MAX_AGE_HOURS}h)"
  # Discard local HTML rebuild so watch-only ticks do not trigger pages.yml.
  git checkout -q -- website docs 2>/dev/null || true
fi

# Always stage watch/reference state (does not trigger pages.yml).
git add -A runs/watch runs/reference || true
if [ "$publish_site" = "1" ]; then
  git add -A website docs || true
fi

if git diff --cached --quiet; then
  echo "no changes to commit"
  exit 0
fi

TS=$(date -u +%Y-%m-%dT%H%MZ)
if [ "$publish_site" = "1" ]; then
  msg="watch+site: $TS ($reason, private host)"
else
  msg="watch: $TS (private host, site deferred)"
fi

git commit -m "$msg"

if [ -n "${ADI_PUSH_TOKEN:-}" ]; then
  git remote set-url origin "https://${ADI_PUSH_TOKEN}@github.com/lemma-ventures/agentic-determinism-index.git"
fi
git push origin main
echo "pushed: $msg"
