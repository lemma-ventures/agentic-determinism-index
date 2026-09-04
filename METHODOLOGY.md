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
5. Tool call and function call response stability is measured as of this revision (`expect: "tool_call"`, §7), with two carried limitations: `gemini` is not covered, and `tool_choice` is left unpinned, so `tool_call_rate` mixes the model's decision to call with the stability of what it calls once it does.

## 7. Tool call cases (`expect: "tool_call"`)

Measures whether a serving stack reproduces the tool invocation a model emits: whether it consistently decides to call the offered tool at all, and whether the call it emits is stable. It does not measure whether the tool itself executes deterministically, and equality between two normalized calls means canonical JSON equality of their arguments, nothing stronger.

### 7.1 Case shape

A `tool_call` case carries a `tools` field: a list of OpenAI Chat Completions style function tool definitions.

```json
{
  "id": "lookup-weather",
  "expect": "tool_call",
  "messages": [{"role": "user", "content": "What is the weather in Lyon?"}],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Look up current weather for a city.",
        "parameters": {
          "type": "object",
          "properties": {"city": {"type": "string"}},
          "required": ["city"]
        }
      }
    }
  ],
  "params": {"temperature": 0, "seed": 42, "max_tokens": 300}
}
```

That shape is the case file's provider neutral input format. Adapters translate it into their own wire format (Anthropic's `name` / `description` / `input_schema` tool object, for example); the translation lives in the adapter, never in generic request or scoring code.

`tools` and `expect: "tool_call"` imply each other. A case carrying one without the other, or a `tools` value that is not a well formed function tool list, fails validation before any request is sent. These are different request and response shapes, and one is never silently run as the other.

The harness sends `tools` without `tool_choice`. Whether to call at all is deliberately left to the model, because that decision is itself part of the behavior under measurement (case 2 below); pinning it would reduce the case type to payload stability alone.

### 7.2 Three response states

Kept distinct, never collapsed into one another:

1. **Valid, with a call** · one or more tool call blocks, each with a name and arguments the adapter can read. Normalizes to the ordered pair list in §7.3. A counted sample.
2. **Valid, with no call** · a well formed model turn (plain text, a refusal, a clarifying question) carrying no tool call block. Also a counted sample. The decision not to call is observable behavior, and excluding these from the denominator would let a model that calls the tool only some of the time look perfectly reproducible over the subset that happened to agree with itself.
3. **Malformed** · a call block is present but cannot be unambiguously interpreted: a missing name, missing arguments, arguments that do not parse as JSON, or a shape the adapter cannot read. An error sample, excluded from `n_ok`, exactly like a transport failure. Never reinterpreted as case 2: the model attempted a call and the harness could not read it, which is a different fact from the model not attempting one.

A provider that does not implement tool call requests at all (§7.5) is a fourth, separate condition: it yields no valid response of either kind, is excluded from `n_ok`, and is never counted as case 2.

### 7.3 Comparable unit

A case 1 response reduces to an ordered list:

```text
[(tool_name, canonical_json(arguments)), ...]
```

Returned order is significant. Parallel calls are never sorted before comparison, so the same calls in a different order score as divergent. Arguments are parsed and re-serialized into the canonical form already used for `expect: "json"` (sorted keys, minimal separators), so object key order and insignificant whitespace do not affect equality while a genuine difference in argument values does. Transport fields the provider attaches to a call, such as a call id or an array index, are excluded from the comparable unit entirely: two responses differing only in those fields normalize to the same value.

A case 2 response normalizes to a distinct tag, not to an empty list, an empty string, or null. It never compares equal to any case 1 outcome, including one with degenerate arguments. "The model called nothing" and "the model called something" are different facts and must stay distinguishable in the representation, not merely in prose.

### 7.4 Metrics

`n`, `n_ok`, and `errors` keep their §3 meaning, except that `n_ok` counts case 1 and case 2 alike, never case 1 only.

- **tool_call_rate** · fraction of valid samples that are case 1.
- **distinct** · number of distinct outcomes, where the case 2 tag and each distinct case 1 call sequence each count as one outcome.
- **byte_identical** · distinct == 1 over those outcomes.
- **mode_share** · (count of most frequent outcome) / n_ok.

A run mixing case 1 and case 2 responses, or two case 1 responses differing in name, arguments, or call order, therefore cannot score `byte_identical: true`. Surfacing that divergence is what these fields are for.

When every valid sample is case 2 (`tool_call_rate == 0`), `distinct`, `byte_identical`, and `mode_share` are omitted rather than published. There is no call payload in the run to claim is reproducible, and `byte_identical: true` over a repeating no call tag, while technically true of the tag, would read as a determinism claim about a payload the run never measured. `n`, `n_ok`, `errors`, `tool_call_rate`, and the fingerprint and model version sets are still reported.

`first_divergence_char` is a text offset and is not reported here: deriving one from an arbitrary serialization of a call outcome would misrepresent what changed between responses. `json_parse_rate` and `distinct_canonical_json` are specific to `expect: "json"` documents and are likewise not reported.

Every sample's transcript records the adapter's extracted call records, including the call ids and indexes excluded from scoring, alongside the normalized outcome actually compared. A third party can audit what was dropped and why two responses were judged equal or different without re-deriving the normalization themselves.

No reference case in this revision uses `expect: "tool_call"`. Before one ships, leaderboard aggregation (§4) needs an explicit rule: `mode_share` here is computed over call outcomes rather than over exact response text, so pooling it with text and json cases into a single ranking would change what the leaderboard number means.

### 7.5 Provider support

`openai`, `openai_compatible`, `nvidia_nim`, `openrouter`, and `huggingface` (OpenAI compatible tool call wire format) and `anthropic` (`tool_use` content blocks) implement `expect: "tool_call"`. `gemini` does not: there is no tested Gemini function calling fixture here to build the mapping against, and guessing the wire format would risk scoring responses incorrectly.

A `tool_call` case run against `gemini` is skipped with a printed reason, and the run's `manifest.json` records the provider, model, case id, and reason under `skipped_tool_call_cases`. No probe file is written for a skipped combination, so a later audit of a run directory can tell a deliberately unsupported target and case pair from one that was never configured to run.

### 7.6 Watch mode

The watch tick (`agentic-determinism-index watch`) sends one cheap, unconditional request per target and carries no case specific tool definitions or provider specific translation logic. `cases/watch/cases.json` must not contain `expect: "tool_call"` cases; if it ever does, the tick refuses to run rather than probing the case as plain text.
