# Contributing

Two ways to contribute: challenge the methodology, or contribute run data.

## Methodology comments

METHODOLOGY.md is a v0.1 draft in a public comment window. Open an issue per point of contention — metric definitions, protocol parameters, confounds (caching, tiering, regions). Disagreements are resolved in the open before any leaderboard publishes.

## Contributing runs (community replications)

Community runs are published as **labeled replications** next to the reference scores — they confirm or contradict from your vantage point (your account tier, your region, your day). They are never merged into the reference leaderboard, so there is no incentive question about whose data "counts"; replications matter precisely because they come from a different vantage point.

To contribute:

1. Run an **unmodified harness at a tagged release** (the manifest records the version; PRs from modified harnesses are rejected on hash mismatch).
2. Use temperature-0 cases from `cases/` or include your custom case file in the PR.
3. Do not edit transcripts. Keys are never written to disk by the harness; there is nothing to redact.
4. Add one fact the manifest can't capture: your **account tier/plan** and **region**, in a `NOTES.md` next to the run.
5. Open a PR placing the run directory at:

```
runs/community/<provider>/<YYYY-MM-DD>-<your-handle>/
├── manifest.json
├── NOTES.md          # account tier, region, anything unusual
└── probes/*.json     # raw transcripts, untouched
```

Review checks: response hashes recompute from transcript text, `score` reproduces your `scores.json`, harness version is a real tag, run meets the minimum sample counts in METHODOLOGY.md §2. That's it — results that contradict the reference runs are exactly as welcome as ones that confirm them.

## Adding a provider

One subclass in `agentic_determinism_index/providers.py` implementing `request(case)` and `parse(body)`, plus a row in the README table. Keep it stdlib-only.
