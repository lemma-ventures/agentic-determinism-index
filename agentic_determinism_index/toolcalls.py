"""Provider-independent normalization for expect: "tool_call" cases.

A structurally valid model response to a tool-enabled request has exactly
one of two observable outcomes: it emits one or more tool calls, or it
emits none. Both are valid data points for a reproducibility measurement;
neither is an error. A response that cannot be interpreted at all (a
missing name, unparseable arguments, an unrecognized shape) is a third,
distinct state: malformed. Conflating "the model chose not to call the
tool" with "the response could not be parsed" would let a model that only
sometimes calls the tool look perfectly reproducible, by silently dropping
every sample where it did not.

normalize_tool_calls therefore returns a tagged outcome:

  NO_TOOL_CALL              the model emitted no tool call block
  a tuple of (name, canonical_arguments) pairs   one or more calls, in order

and raises ToolCallParseError only when a tool call block is present but
cannot be unambiguously normalized. A malformed record is never
reinterpreted as NO_TOOL_CALL, and NO_TOOL_CALL never compares equal to
any tuple of calls, including an empty one.

Transport fields (call id, index, ...) never participate in normalization:
two raw records with the same name and semantically equivalent arguments
normalize to the same value regardless of those fields. Call order is
preserved and is significant.
"""
import json

from .metrics import canonical_json


class ToolCallParseError(ValueError):
    """A provider's tool-call payload could not be unambiguously normalized."""


class NoToolCall:
    """Singleton tag for a structurally valid model response containing no
    tool call. Distinct from every possible TOOL_CALL outcome (a tuple)
    and from a malformed response, which raises ToolCallParseError instead
    of producing this value. Use the module-level NO_TOOL_CALL instance,
    never construct this directly."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __eq__(self, other):
        return isinstance(other, NoToolCall)

    def __hash__(self):
        return hash(NoToolCall)

    def __repr__(self):
        return "NO_TOOL_CALL"


NO_TOOL_CALL = NoToolCall()


def normalize_arguments(raw):
    """Turn provider-returned arguments into a canonical JSON string.

    ``raw`` is either a JSON-encoded string (the OpenAI Chat Completions
    shape) or an already-parsed JSON value (the Anthropic Messages shape).
    Both paths produce the same canonical form via the same json.dumps
    parameters used by metrics.canonical_json, so equality does not depend
    on which provider produced the value.
    """
    if raw is None:
        raise ToolCallParseError("arguments missing")
    if isinstance(raw, str):
        canon = canonical_json(raw)
        if canon is None:
            raise ToolCallParseError(f"arguments is not valid JSON: {raw!r}")
        return canon
    try:
        return json.dumps(raw, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as e:
        raise ToolCallParseError(f"arguments not JSON-serializable: {e}") from None


def normalize_tool_call(raw_call):
    """raw_call is a dict with at least "name" and "arguments" keys, as
    produced by a provider adapter's extraction step for one emitted call.
    Any other keys (id, index, ...) are ignored. Returns a
    (name, canonical_arguments) tuple."""
    if not isinstance(raw_call, dict):
        raise ToolCallParseError(f"tool call is not an object: {raw_call!r}")
    name = raw_call.get("name")
    if not isinstance(name, str) or not name:
        raise ToolCallParseError(f"tool call missing a name: {raw_call!r}")
    arguments = normalize_arguments(raw_call.get("arguments"))
    return (name, arguments)


def normalize_tool_calls(raw_calls):
    """Order-preserving normalization of a provider adapter's raw
    extraction result for one response.

    ``raw_calls`` is None or an empty list when the adapter found no tool
    call block in the response: a structurally valid outcome, returned
    here as NO_TOOL_CALL, not an error. A non-empty list is normalized
    entry by entry into an ordered tuple of (name, canonical_arguments)
    pairs. If any entry in a non-empty list cannot be unambiguously
    normalized, ToolCallParseError propagates and the whole response is
    invalid: a malformed call is never folded into NO_TOOL_CALL or into a
    partial result.
    """
    if not raw_calls:
        return NO_TOOL_CALL
    return tuple(normalize_tool_call(c) for c in raw_calls)
