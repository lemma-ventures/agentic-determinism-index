# Runs

- `reference/` — maintainer runs on a fixed cadence; the only data feeding published leaderboard scores (see METHODOLOGY.md §4).
- `community/` — contributed replications, labeled and published alongside; see CONTRIBUTING.md for the PR format.
- `local/` — gitignored scratch space for your own experiments (`--out runs/local`).

Every run directory contains `manifest.json` plus raw transcripts under `probes/`; `python3 -m agentic_determinism_index score <run-dir>` regenerates its scores exactly.
