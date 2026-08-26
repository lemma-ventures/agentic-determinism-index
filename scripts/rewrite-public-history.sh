#!/usr/bin/env bash
# Rewrite to a single clean commit. Full procedure: DLM/content/PUBLIC_REPO_PUBLISH.md
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .git ]]; then
  echo "ERROR: not a git repo: $ROOT" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree not clean. Commit or stash first." >&2
  git status --short
  exit 1
fi

if [[ -d templates ]]; then
  echo "ERROR: templates/ still exists — remove before rewrite." >&2
  exit 1
fi

if git grep -q 'staging.lemma.ventures/preview' HEAD -- ':!scripts/' 2>/dev/null; then
  echo "ERROR: preview URLs found in current tree." >&2
  exit 1
fi

echo "Running tests..."
python3 -m pytest -q

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "ERROR: expected branch main, on $CURRENT_BRANCH" >&2
  exit 1
fi

echo "Creating orphan branch public-clean..."
git checkout --orphan public-clean
git add -A
git commit -m "$(cat <<'EOF'
Initial public release: Agentic Determinism Index harness (MIT).

Open harness and methodology for measuring byte-level reproducibility on
hosted LLM APIs. Methodology publishes before reference scores; scores follow
a public comment window.

Maintained by Lemma Ventures. See README for maintainer disclosure.
EOF
)"

git branch -D main
git branch -m main

echo ""
echo "OK — main is now a single commit:"
git log --oneline
echo ""
echo "Next: verify then git push --force-with-lease origin main"
echo "See DLM/content/PUBLIC_REPO_PUBLISH.md"
