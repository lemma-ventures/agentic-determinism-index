# Agentic Determinism Index (ADI) · Methodology (v0.1 draft)

Status: **open for public comment** while first reference scores ship. Challenge any definition below via issues; scores stay recomputable from transcripts and will be revised if the protocol changes.

## 1. Question under measurement

For a fixed serving tuple **T = (provider, model identifier, parameter set, endpoint)** and a fixed request **R**: how identical are the responses to N transmissions of R, (a) under concurrent load, (b) spaced in time within a run, and (c) across days?

This measures the *serving stack's* reproducibility. It does not measure output quality, and it does not measure semantic stability under rephrasing (a deterministic stack still answers a paraphrased question differently · that is a different, harder property, out of scope for v0.1).

## 2. Probe protocol

Per (target, case), one **run** consists of:

- **Burst:** N_b identical requests fired concurrently (default 10). Exposes batch-composition sensitivity: whether your answer depends on what else the fleet is serving.
- **Serial:** N_s identical requests spaced by a gap (default 3 requests, 60 s apart). Exposes short-horizon variance without self-induced batching.
- **Drift window:** runs repeated across days (recommended ≥ 3 runs over ≥ 72 h) under an unchanged config. Exposes fleet/engine/version drift, via response changes and fingerprint/version fields where the API exposes them.

Requests are byte-identical within a run: same prompt bytes, same parameters, same serialization. `temperature` is 0 for all v0.1 cases; `seed` is set and recorded where the API accepts one. The full request except credentials is stored in the transcript.

## 3. Metrics

Over the n_ok non-error responses to one (target, case) run, with each response taken as its exact returned text:

- **distinct** · |{responses}|.
- **byte_identical** · distinct == 1.
- **mode_share** · (count of most frequent response) / n_ok.
- **first_divergence_char** · smallest character index at which any two responses differ; length of the shortest response if one is a strict prefix of another; null when identical. Character-level rather than token-level, deliberately: token metrics require provider-specific tokenizers, which would make scores harder for third parties to reproduce. (Open question §6.)
- **Structured cases** (`expect: "json"`): **json_parse_rate**, and **distinct_canonical_json** after parsing and canonical re-serialization (sorted keys, minimal separators). Separates surface-form variance from semantic variance in structured output.
- **Drift:** set of `system_fingerprint` / `modelVersion` values observed; a change across the window under an unchanged config is a drift event.

Errors are counted and excluded from divergence metrics; a run with n_ok < N/2 is not scored.

## 4. Scoring and aggregation

Per target, per run: metrics are reported per case, plus a **worst-case row** (the case with the lowest mode_share). Cross-run aggregation over the drift window reports the range, not just the mean · a stack that is identical within a day but drifts across days must not average into a good score.

Leaderboard scores come exclusively from maintainer **reference runs** (fixed cadence, disclosed harness version, config hash, account tier, region). Community-contributed runs are published as labeled **replications** and never pooled into reference scores, because provider behavior varies by account tier, region, and routing.

## 5. Reproducibility of the measurement itself

Every published score ships with: the manifest (harness version, platform, config and case hashes, timestamps), raw transcripts, and per-response SHA-256 hashes. `python3 -m agentic_determinism_index score <run-dir>` must reproduce the published numbers exactly. The harness is stdlib-only so the measurement has no dependency drift of its own.

## 6. Known limitations / open questions (v0.1)

1. No token-level divergence metric (tokenizer dependency vs reproducibility trade-off · proposals welcome).
2. Judge/eval variance (how much run-to-run divergence moves LLM-judge verdicts) is planned as a separate protocol; no number is claimed until it is measured here.
3. Streaming vs non-streaming responses may differ; v0.1 probes non-streaming only.
4. Provider-side caching can mask variance (identical answers because you got a cache hit, not a deterministic recompute). The serial-gap and cross-day protocol partially controls for this; flagged as an open confound.
5. Tool-call/function-call response stability is not yet a case type.
