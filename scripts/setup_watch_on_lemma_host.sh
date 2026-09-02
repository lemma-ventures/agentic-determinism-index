#!/usr/bin/env bash
# Setup + runner for ADI private watch on the lemma.ventures host (lemma-web box).
# Run this once as the user that owns the GitHub runner (or root, then chown).
# It:
#   - Clones (or updates) the ADI repo to /opt/adi-watch
#   - Installs the harness
#   - Creates a secure env file for keys (you paste them)
#   - Installs a systemd timer for hourly execution (or falls back to cron)
#   - The tick script runs ci_watch.sh, commits, and pushes results
#     (triggers GitHub Pages via docs/ + website/ push)
#
# Secrets policy: keys live ONLY in /etc/adi-watch.env on this private box.
# Never in the public ADI repo, never as GitHub Actions secrets on lemma-ventures/agentic-determinism-index.
set -euo pipefail

WATCH_DIR=/opt/adi-watch
ENV_FILE=/etc/adi-watch.env
TICK_SCRIPT=/usr/local/bin/adi-watch-tick
UNIT_DIR=/etc/systemd/system
RUN_USER="${SUDO_USER:-$USER}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo $0"
  exit 1
fi

echo "==> Preparing $WATCH_DIR (owned by $RUN_USER)"
mkdir -p "$WATCH_DIR"
chown "$RUN_USER":"$RUN_USER" "$WATCH_DIR"

if [ ! -d "$WATCH_DIR/.git" ]; then
  echo "==> Fresh clone"
  sudo -u "$RUN_USER" git clone https://github.com/lemma-ventures/agentic-determinism-index.git "$WATCH_DIR"
else
  echo "==> Updating existing clone"
  (cd "$WATCH_DIR" && sudo -u "$RUN_USER" git fetch origin main && sudo -u "$RUN_USER" git checkout main && sudo -u "$RUN_USER" git pull --ff-only)
fi

echo "==> Install harness (python -e .)"
(cd "$WATCH_DIR" && sudo -u "$RUN_USER" python3 -m pip install -e . --quiet)

if [ ! -f "$ENV_FILE" ]; then
  echo "==> Creating $ENV_FILE (0600). Paste your keys now."
  cat > "$ENV_FILE" <<'EOT'
# ADI private watch env — lemma.ventures box only
# Rotate by editing this file + systemctl restart adi-watch.timer
OPENROUTER_API_KEY=
NVIDIA_API_KEY=
# For git push (fine-grained PAT with contents:write on lemma-ventures/agentic-determinism-index)
ADI_PUSH_TOKEN=
EOT
  chmod 600 "$ENV_FILE"
  chown root:root "$ENV_FILE"
  echo "Edit $ENV_FILE and fill the three values, then re-run this script or continue manually."
  echo "Get ADI_PUSH_TOKEN from GitHub → Settings → Developer settings → Personal access tokens (fine-grained, repo: lemma-ventures/agentic-determinism-index, permissions: Contents: Read and write)."
fi

echo "==> Writing tick script $TICK_SCRIPT"
cat > "$TICK_SCRIPT" <<'TICK'
#!/usr/bin/env bash
set -euo pipefail

WATCH_DIR=/opt/adi-watch
ENV_FILE=/etc/adi-watch.env

if [ ! -f "$ENV_FILE" ]; then
  echo "missing $ENV_FILE" >&2
  exit 1
fi

# Load secrets (never logged)
set -a
. "$ENV_FILE"
set +a

export OPENROUTER_API_KEY
export NVIDIA_API_KEY

cd "$WATCH_DIR"

echo "==> git pull"
git fetch origin main
git checkout main
git pull --ff-only || true

echo "==> run watch tick"
  export WATCH_DIR=runs/watch
  export RUN_ROOT=runs/reference
  mkdir -p "$WATCH_DIR" "$RUN_ROOT"

  # Use the same harness entry as ci_watch.sh (continues on drift)
  set +e
  ./scripts/ci_watch.sh
  WATCH_RC=$?
  set -e

  echo "==> commit & push if dirty (watch_rc=$WATCH_RC)"
git config user.name "lemma-web watch"
git config user.email "watch@lemma.ventures"
git add -A runs/watch runs/reference website docs || true

if git diff --cached --quiet; then
  echo "no changes"
else
  TS=$(date -u +%Y-%m-%dT%H%MZ)
  git commit -m "watch: $TS (private host)"
  if [ -n "${ADI_PUSH_TOKEN:-}" ]; then
    git remote set-url origin "https://${ADI_PUSH_TOKEN}@github.com/lemma-ventures/agentic-determinism-index.git"
  fi
  git push origin main
fi

echo "adi-watch tick done"
TICK
chmod +x "$TICK_SCRIPT"
chown root:root "$TICK_SCRIPT"

echo "==> Installing systemd timer (hourly, offset :17 like the old cron)"
cat > "$UNIT_DIR/adi-watch.service" <<'SVC'
[Unit]
Description=ADI private watch tick (hourly cheap + due full scores)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/adi-watch-tick
User=root
# Protect the env file
ProtectSystem=full
ReadWritePaths=/opt/adi-watch
NoNewPrivileges=true
StandardOutput=journal
StandardError=journal
SVC

cat > "$UNIT_DIR/adi-watch.timer" <<'TMR'
[Unit]
Description=Run ADI watch every hour at :17

[Timer]
OnCalendar=*-*-* *:17:00
Persistent=true
Unit=adi-watch.service

[Install]
WantedBy=timers.target
TMR

systemctl daemon-reload
systemctl enable --now adi-watch.timer

echo "==> Verify"
systemctl list-timers --all | grep adi-watch || true
echo
echo "Done."
echo "Edit $ENV_FILE with real keys + ADI_PUSH_TOKEN (then: systemctl restart adi-watch.timer)"
echo "Logs: journalctl -u adi-watch -f"
echo "Manual tick: sudo /usr/local/bin/adi-watch-tick"
