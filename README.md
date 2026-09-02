# Agentic Determinism Index (ADI)

A public harness that asks one narrow question of hosted LLM APIs:

> **If I send you the exact same request N times, concurrently, and again across days, how identical are your answers?**

No benchmark of intelligence, no quality judgment. Just reproducibility, measured at the byte level, per model, over time, from raw transcripts anyone can re-score.

- **Zero dependencies.** Python ≥ 3.9 standard library only. Clone and run.
- **Methodology open, scores live.** The harness and scoring spec ([METHODOLOGY.md](METHODOLOGY.md), v0.1 draft) ship with the first reference leaderboard. Challenge any metric via issues; scores remain recomputable from transcripts and update as new reference runs land.
- **A door, not a wall.** Alongside scores we document the exact conditions a provider would need to meet for reproducible serving. Providers that meet them get recognized for it.

## Quickstart

```bash
git clone <this-repo> && cd agentic-determinism-index

# keys for whichever providers you want to probe (only the ones you set are usable;
# unset providers are skipped automatically)
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GEMINI_API_KEY=...
export NVIDIA_API_KEY=...
export OPENROUTER_API_KEY=...
export HF_API_KEY=...

# edit configs/example.json to the models you care about, then:
python3 -m agentic_determinism_index run --config configs/example.json
python3 -m agentic_determinism_index score runs/reference/<timestamp>
python3 -m agentic_determinism_index site --run runs/reference/<timestamp> --out website/index.html
```

`run` fires each probe case at each target, a concurrent burst plus spaced serial requests, and writes raw transcripts (`probes/*.json`) plus an environment manifest. `score` turns a run directory into `scores.json` and a human-readable `SCORES.md`. `site` renders a standalone leaderboard page from `scores.json` into a static HTML file. Nothing is uploaded anywhere; everything stays on your disk unless you choose to contribute it.

## What it measures

Per (provider, model, case):

| Metric | Meaning |
|---|---|
| `byte_identical` | All N responses bit-for-bit identical |
| `distinct` | Number of distinct completions observed |
| `mode_share` | Fraction of responses matching the most common completion |
| `first_divergence_char` | Character index where responses first differ |
| `json_parse_rate` / `distinct_canonical_json` | Structured-output stability: does the *parsed, canonicalized* JSON agree even when bytes don't |
| `fingerprints` / `model_versions` | Backend fingerprint and version drift observed across the run window |

Definitions and the probe protocol are specified in [METHODOLOGY.md](METHODOLOGY.md).

## How this relates to the model or agent *you* are using

The scores here do not describe a model. They describe a **serving tuple**: (provider, model snapshot, parameters, serving stack) during a time window. The same weights served two different ways will score differently, determinism is a property of the deployment, not the weights.

That matters for you in three concrete ways:

1. **Your agent inherits the reproducibility of the exact tuple it calls.** If your agent calls `some-model-2026-05-13` at temperature 0 with a tool schema, its reproducibility is that tuple's, not the model family's, and not what this repo measured for a different snapshot or parameter set. To measure *your* stack, copy your production request shape (same model string, temperature, seed, max tokens, JSON/tool schema) into a case file under `cases/` and run the harness against it. The closer the probe is to your real traffic, the more the score means.

2. **Probe through the same path your agent uses.** If your requests go through a gateway, proxy, or router, that layer is part of your stack, point the harness at it, not at the provider directly. Any OpenAI-compatible endpoint works via the `openai_compatible` provider with a `base_url`, which also means you can probe a self-hosted vLLM/SGLang deployment and compare it against hosted APIs under identical cases.

3. **Multi-step agents compound single-step variance.** A single flipped token early in a plan can change every subsequent action. If a model's `mode_share` is 0.8 per call, a 10-call agent trajectory repeats far less often than 80% of the time. When your agent tests are flaky, this harness tells you how much of that is the serving layer before you debug your own code.

## How scores are aggregated

Two strictly separated tiers:

- **Reference runs**, the only data that feeds the published leaderboard. Executed by the maintainers on a fixed cadence, with disclosed harness version, config, account tier, and region. Provider behavior varies by account tier, region, and routing, so leaderboard comparability requires a controlled, uniform vantage point.
- **Community replications**, contributed runs, published alongside the leaderboard as labeled replications that confirm or contradict the reference scores from other vantage points (different tiers, regions, days). They are never merged into reference scores. Contributing your data is a PR: see [CONTRIBUTING.md](CONTRIBUTING.md).

Every published score, reference or community, is recomputable from its raw transcripts with `python3 -m agentic_determinism_index score`. A score you can't re-derive doesn't get published.

For public publication, run:

```bash
python3 -m agentic_determinism_index site --run-root runs/reference --out website/index.html
```

Then commit only `website/index.html` (or equivalent generated directory) alongside the corresponding reference run if you are maintaining a mirrored leaderboard. The generated page now includes an on-page `Stack-drift timeline` section that tracks `(provider, model)` stack-ID changes (`system_fingerprint` and `modelVersion`) across your scored reference run history.

## Supported providers

| `provider` | API | Notes |
|---|---|---|
| `openai` | Chat Completions | records `system_fingerprint`; `seed` sent when set |
| `anthropic` | Messages | no seed parameter exists; probed at temperature 0 |
| `gemini` | generateContent | `seed` sent when set; records `modelVersion` |
| `openai_compatible` | any Chat-Completions-shaped endpoint | set `base_url`: gateways, routers, self-hosted vLLM/SGLang |
| `nvidia_nim` | NIM chat (OpenAI-compatible) | default base hosted NIM. NIM's deterministic mode (`NIM_FORCE_DETERMINISTIC`) is documented as a container env var for self-hosted deployments, not as a hosted-API parameter; to measure it, self-host a NIM with the variable set and probe it via `openai_compatible` |
| `openrouter` | OpenRouter (OpenAI-compatible) | routes to shifting upstream backends; expect poor burst scores. Routed `provider` recorded as fingerprint |
| `huggingface` | HF Router / Inference Endpoint (OpenAI-compatible) | default base is the HF Router; set `base_url` to a dedicated Endpoint to probe one pinned deployment |

Adding a provider is one adapter class in `agentic_determinism_index/providers.py`.

## Status

v0.1, methodology comment window open, first reference scores published and updated continuously. License: [MIT](LICENSE).

## Maintained by

**Lemma Ventures AG**, Zug, Switzerland, which builds deterministic-inference infrastructure.

**Incentive disclosure:** Lemma has commercial interest in reproducible serving. This harness exists so published scores do not require trusting the maintainer: every score is recomputable from raw transcripts with `python3 -m agentic_determinism_index score`. Community replications are welcome; the reference leaderboard column is maintainer-controlled for tier/region comparability.

This repo measures serving reproducibility. It does not implement pinned-stack serving, receipts, or replay infrastructure.

## Hosting the leaderboard site

The `site` command emits a single-file, self-contained `website/index.html` (no external assets, no tracking).

**Live links (use these):**

| Host | URL |
|---|---|
| GitHub repo | https://github.com/lemma-ventures/agentic-determinism-index |
| Canonical index (GitHub Pages) | https://lemma-ventures.github.io/agentic-determinism-index/ |

- **Scores page:** single-purpose leaderboard only. Footer names Lemma; no product CTAs.
- **Do not embed** the live leaderboard inside marketing pages. Other Lemma properties link **out** by URL.

**Medals:** each published snapshot ranks reference tuples; top 3 receive 🥇🥈🥉 (most reproducible under the disclosed protocol). Medals are snapshot-relative, not permanent certifications.

Bootstrap reference scores ship with the harness. A **first analysis follows after about a month** of continuous runs and open-source community contributions. Until then the page shows the latest bootstrap reference run and updates as new runs land.

### Continuous watch (private host only)

GitHub Pages only serves static HTML. Provider probing needs API keys.

**This public repository must never store provider API keys** (no GitHub Actions secrets for `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`, or similar). Continuous watch runs on a **private machine or private runner** with keys in the process environment only. Publish results by PR of `runs/` + `website/` artifacts.

| Cadence | What |
|---|---|
| Hourly (or as scheduled privately) | `watch` cheap stack-ID tick (1 short request per due target) |
| After stable ticks | Interval backs off (1.5x) up to 24h; known non-exact stacks cap at 7d |
| Full score | Byte-exact tuples about daily; **non-exact about monthly** (`--due-only`) |

#### On the lemma.ventures host (recommended)

The production box (self-hosted runner label `lemma-web`) already serves the site via Caddy. Use it for the private watch.

```bash
# On the box (via SSH or a one-off Actions step on the website repo that targets [self-hosted, lemma-web])
sudo bash scripts/setup_watch_on_lemma_host.sh
```

Edit `/etc/adi-watch.env` (root-only) with:
- `OPENROUTER_API_KEY`
- `NVIDIA_API_KEY` (optional)
- `ADI_PUSH_TOKEN` (fine-grained PAT: Contents read+write on `lemma-ventures/agentic-determinism-index` only)

Then:
```bash
sudo systemctl restart adi-watch.timer
journalctl -u adi-watch -f
```

The timer runs at :17 past the hour (same offset as the old public cron). It pulls, runs `ci_watch.sh`, commits `runs/watch/`, `runs/reference/`, `website/`, `docs/`, and pushes. The push triggers `pages.yml` automatically.

Manual one-off:
```bash
sudo /usr/local/bin/adi-watch-tick
```

Fallback to cron (if no systemd):
```bash
echo '17 * * * * root /usr/local/bin/adi-watch-tick >> /var/log/adi-watch.log 2>&1' | sudo tee /etc/cron.d/adi-watch
```

#### Local / other private host

```bash
export OPENROUTER_API_KEY=...
export NVIDIA_API_KEY=...
./scripts/ci_watch.sh
```

State lives in `runs/watch/` so backoff survives across runs. Commit and push artifacts when you want the public index updated.

To publish a snapshot:
```bash
python3 -m agentic_determinism_index site --run-root runs/reference --out website/index.html
git add website/index.html runs/reference/<stamp> && git commit -m "publish leaderboard for <stamp>"
git push origin main
```
GitHub Pages is served from `/docs` on `main` (GitHub only allows `/` or `/docs` for legacy Pages). `website/index.html` remains the build output; copy or regenerate into `docs/` when publishing.

## Background and motivation

Read the author's launch post for the full context and thoughts behind the Agentic Determinism Index:

https://lemma.ventures/blog/your-model-is-not-non-deterministic.html
