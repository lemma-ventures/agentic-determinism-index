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
5. Tool call and function call response stability is a case type as of this revision: `expect: "tool_call"`. See §7 for the comparable unit, the call versus no call versus malformed distinction, provider support, and metrics. A case that specifies `tools` without `expect: "tool_call"`, or vice versa, is rejected at run time rather than run under a mismatched shape.

## 7. Tool call cases (`expect: "tool_call"`)

This case type measures reproducibility of the model's emitted tool invocation structure across repeated identical requests: whether the model consistently decides to call the offered tool at all, and, when it does, whether the call it emits is stable. It does not measure whether the tool itself executes deterministically, and it does not claim that two normalized calls are semantically equivalent beyond canonical JSON equality of their arguments.

### 7.1 Case shape

A `tool_call` case carries a `tools` field: a list of OpenAI Chat Completions style function tool definitions, for example:

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

This tool shape is the case file's provider neutral input format. Provider adapters translate it into their own wire format (for example Anthropic's `name`/`description`/`input_schema` tool object); the translation lives in the adapter, never in generic request or scoring code. A case with `expect: "tool_call"` and no `tools`, or with a `tools` value that is not a well formed function tool list, fails validation before any request is sent. A case with `tools` and `expect` other than `tool_call` is rejected the same way: these are distinct request and response shapes, and one is never silently treated as the other.

### 7.2 Three response states

A structurally valid model response to a tool enabled request has exactly one of two observable outcomes, and a response can additionally fail to be interpretable at all. These three states are kept distinct and are never collapsed into one another:

1. **Valid, with a call.** The response contains one or more tool call blocks, each with a name and arguments the adapter can read. This normalizes to an ordered list of `(tool_name, canonical_json(arguments))` pairs, described in §7.3. This is a counted, successful sample.
2. **Valid, with no call.** The response is a well formed model turn (plain text, a refusal, a clarifying question, anything) that contains no tool call block at all. This is also a counted, successful sample: the model's decision not to call the tool is itself part of its observable behavior, and excluding these samples from the reproducibility denominator would let a model that only sometimes calls the tool look perfectly reproducible by measuring only the times it happened to agree with itself.
3. **Malformed.** A tool call block is present but cannot be unambiguously interpreted: a missing name, missing arguments, arguments that do not parse as JSON, or a response shape the adapter cannot read. This is an error sample, excluded from `n_ok`, exactly like a transport failure. A malformed response is never reinterpreted as case 2: the model attempted a call and the harness could not read it, which is a different fact than the model not attempting a call.

A provider or adapter that cannot support tool call requests at all (see §7.5) is a fourth, separate condition: it produces no valid response of either kind and is likewise excluded from `n_ok`, never counted as case 2.

### 7.3 Comparable unit

A case 1 response is reduced to an ordered list of normalized tool calls:

```text
[(tool_name, canonical_json(arguments)), ...]
```

Order in the returned list is significant. Two responses containing the same calls in a different order are scored as divergent; parallel calls are never sorted before comparison. Arguments are parsed as JSON and converted to the same canonical form already used for `expect: "json"` cases (sorted keys, minimal separators), so object key order and insignificant whitespace do not affect equality while a genuine difference in argument values does. Transport fields attached to a call by the provider, such as a call id or an array index, are excluded from the comparable unit entirely: two responses that differ only in those fields normalize to the same value.

A case 2 response (no call) normalizes to a distinct tag, not to an empty list, an empty string, or null. It never compares equal to any case 1 outcome, including a case 1 outcome with degenerate arguments: "the model called nothing" and "the model called something" are different facts and must remain distinguishable in the comparable representation, not merely in prose.

### 7.4 Metrics

`n`, `n_ok`, and `errors` carry their usual meaning; `n_ok` counts both case 1 and case 2 responses, never only case 1. `tool_call_rate` is the fraction of valid (`n_ok`) samples that are case 1: at least one tool call emitted.

Over the full set of valid samples, `distinct` counts distinct outcomes (a case 2 no call outcome and every distinct case 1 call sequence each count as one outcome), `byte_identical` is true when every valid sample produced the same outcome, and `mode_share` is the fraction of samples matching the most common outcome. A run mixing case 1 and case 2 responses, or two case 1 responses with different names, arguments, or call order, therefore cannot score as `byte_identical: true`: the divergence in what the model did is exactly what these fields exist to surface.

When every valid sample in a run is case 2 (`tool_call_rate == 0`), `distinct`, `byte_identical`, and `mode_share` are omitted entirely rather than published. There is no call payload in that run to claim is reproducible; reporting `byte_identical: true` in that situation, even though it would be technically true of the no call tag repeating, would read as a claim of tool call payload determinism that the run never measured. `tool_call_rate: 0.0` together with the missing payload fields is the documented way this case is reported: a reader sees plainly that the model never called the tool, and no reproducibility claim is made about a payload that does not exist. `n`, `n_ok`, `errors`, `tool_call_rate`, and the fingerprint and model version sets are still reported in this situation.

`first_divergence_char` is not reported for this case type: it is a text offset, and fabricating one over an arbitrary serialization of a call outcome would misrepresent what changed between responses. `json_parse_rate` and `distinct_canonical_json` are specific to `expect: "json"` document responses and are likewise not reported here.

The raw provider response (including any tool call ids or indexes) and the normalized outcome scoring actually used are both stored in the transcript for every sample, so a third party can audit exactly what was excluded and why two responses were judged equal or different without independently deriving the normalization from the raw bytes alone.

### 7.5 Provider support

`openai`, `openai_compatible`, `nvidia_nim`, `openrouter`, and `huggingface` (all OpenAI compatible tool call wire formats) and `anthropic` (`tool_use` content blocks) implement `expect: "tool_call"`. `gemini` does not: this harness has no tested Gemini function calling fixture to build the mapping against, and guessing the wire format would risk scoring responses incorrectly. A `tool_call` case run against `gemini` is skipped explicitly, with a printed reason, and the run's `manifest.json` records the provider, model, case id, and reason under `skipped_tool_call_cases`, so a later audit of the run directory can distinguish a target and case combination that was deliberately skipped as unsupported from one that was never configured to run at all. No probe file is written for a skipped combination.

### 7.6 Watch mode

The watch tick (`agentic-determinism-index watch`) sends one cheap, unconditional request per target and carries no case specific tool definitions or provider specific tool translation logic. `cases/watch/cases.json` must not contain `expect: "tool_call"` cases; if it ever does, the watch tick refuses to run rather than probing the case as plain text.
