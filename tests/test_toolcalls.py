import json
import os
import tempfile
import unittest

from agentic_determinism_index.cli import main as cli_main
from agentic_determinism_index.metrics import score_samples
from agentic_determinism_index.probe import one_call, validate_cases
from agentic_determinism_index.providers import (
    AnthropicMessages,
    GeminiGenerate,
    OpenAIChat,
    OpenRouter,
    tool_call_supported,
)
from agentic_determinism_index.toolcalls import (
    NO_TOOL_CALL,
    ToolCallParseError,
    normalize_arguments,
    normalize_tool_call,
    normalize_tool_calls,
)
from agentic_determinism_index.watch import run_tick


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Look up current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]

TOOL_CASE = {
    "id": "lookup-weather",
    "expect": "tool_call",
    "messages": [{"role": "user", "content": "Weather in Lyon?"}],
    "tools": TOOLS,
    "params": {"temperature": 0, "seed": 42, "max_tokens": 300},
}


# ---------------------------------------------------------------------------
# A. Case validation
# ---------------------------------------------------------------------------

class TestCaseValidation(unittest.TestCase):
    def test_valid_tool_call_case_accepted(self):
        validate_cases([TOOL_CASE])  # must not raise

    def test_existing_text_and_json_cases_still_valid(self):
        validate_cases([
            {"id": "t", "expect": "text", "messages": []},
            {"id": "j", "expect": "json", "messages": []},
            {"id": "default-expect", "messages": []},
        ])

    def test_tool_call_without_tools_rejected(self):
        with self.assertRaises(SystemExit) as ctx:
            validate_cases([{"id": "no-tools", "expect": "tool_call", "messages": []}])
        self.assertIn("no 'tools'", str(ctx.exception))

    def test_tools_without_tool_call_expect_rejected(self):
        with self.assertRaises(SystemExit) as ctx:
            validate_cases([{"id": "with-tools", "tools": TOOLS, "messages": []}])
        self.assertIn("unsupported combination", str(ctx.exception))

    def test_malformed_tools_shape_rejected(self):
        bad_shapes = [
            [{"type": "function", "function": {}}],           # missing name
            [{"type": "function"}],                            # missing function
            [{"type": "not-a-function", "function": {"name": "x"}}],
            "not-a-list",
            [],
        ]
        for tools in bad_shapes:
            with self.subTest(tools=tools):
                case = {"id": "bad", "expect": "tool_call", "messages": [], "tools": tools}
                with self.assertRaises(SystemExit):
                    validate_cases([case])


# ---------------------------------------------------------------------------
# B. Request construction
# ---------------------------------------------------------------------------

class TestRequestConstruction(unittest.TestCase):
    def test_tool_call_case_sends_tools_openai(self):
        p = OpenAIChat({"provider": "openai", "model": "m"})
        req = p.request(TOOL_CASE)
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["tools"], TOOLS)

    def test_text_case_does_not_receive_tools(self):
        p = OpenAIChat({"provider": "openai", "model": "m"})
        req = p.request({"id": "t", "expect": "text",
                          "messages": [{"role": "user", "content": "hi"}]})
        payload = json.loads(req.data.decode("utf-8"))
        self.assertNotIn("tools", payload)

    def test_json_case_keeps_response_format_shape(self):
        p = OpenAIChat({"provider": "openai", "model": "m"})
        req = p.request({
            "id": "j", "expect": "json",
            "messages": [{"role": "user", "content": "hi"}],
            "params": {"json": True},
        })
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertNotIn("tools", payload)

    def test_openrouter_forwards_tools(self):
        p = OpenRouter({"provider": "openrouter", "model": "m"})
        req = p.request(TOOL_CASE)
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["tools"], TOOLS)

    def test_anthropic_translates_tools(self):
        p = AnthropicMessages({"provider": "anthropic", "model": "m"})
        req = p.request(TOOL_CASE)
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["tools"], [{
            "name": "get_weather",
            "description": "Look up current weather for a city.",
            "input_schema": TOOLS[0]["function"]["parameters"],
        }])

    def test_gemini_rejects_tool_call_case(self):
        p = GeminiGenerate({"provider": "gemini", "model": "m"})
        with self.assertRaises(NotImplementedError):
            p.request(TOOL_CASE)

    def test_request_hash_distinguishes_tools_from_no_tools(self):
        p = OpenAIChat({"provider": "openai", "model": "m"})
        plain = {"id": "t", "expect": "text",
                 "messages": [{"role": "user", "content": "hi"}]}
        req_plain = p.request(plain)
        req_tool = p.request(TOOL_CASE)
        self.assertNotEqual(req_plain.data, req_tool.data)

    def test_tool_call_supported_matrix(self):
        for provider in ("openai", "openai_compatible", "anthropic",
                         "nvidia_nim", "openrouter", "huggingface"):
            self.assertTrue(tool_call_supported(provider), provider)
        self.assertFalse(tool_call_supported("gemini"))


# ---------------------------------------------------------------------------
# C. OpenAI style parsing and the call / no-call / malformed split
# ---------------------------------------------------------------------------

def openai_body(tool_calls=None, content=None):
    message = {"content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {"choices": [{"message": message}], "model": "gpt-test"}


class FakeProvider:
    """Wraps a canned parse() result, or a raised exception, so one_call()
    can be exercised without a network call."""
    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc

    def call(self, case, timeout=180):
        if self._exc:
            raise self._exc
        return self._result


class TestOpenAIParsing(unittest.TestCase):
    def test_single_call_extracted(self):
        p = OpenAIChat({"provider": "openai", "model": "m"})
        body = openai_body(tool_calls=[
            {"id": "call_1", "type": "function",
             "function": {"name": "get_weather", "arguments": '{"city":"Lyon"}'}},
        ])
        parsed = p.parse(body)
        self.assertEqual(parsed["tool_calls"],
                         [{"name": "get_weather", "arguments": '{"city":"Lyon"}', "id": "call_1"}])

    def test_multiple_calls_preserve_order(self):
        p = OpenAIChat({"provider": "openai", "model": "m"})
        body = openai_body(tool_calls=[
            {"id": "1", "function": {"name": "a", "arguments": "{}"}},
            {"id": "2", "function": {"name": "b", "arguments": "{}"}},
        ])
        parsed = p.parse(body)
        self.assertEqual([c["name"] for c in parsed["tool_calls"]], ["a", "b"])

    def test_id_change_does_not_affect_normalized_equality(self):
        raw_a = [{"id": "call_1", "name": "f", "arguments": '{"x":1}'}]
        raw_b = [{"id": "call_2", "name": "f", "arguments": '{"x":1}'}]
        self.assertEqual(normalize_tool_calls(raw_a), normalize_tool_calls(raw_b))

    def test_index_change_does_not_affect_normalized_equality(self):
        raw_a = [{"index": 0, "name": "f", "arguments": '{"x":1}'}]
        raw_b = [{"index": 7, "name": "f", "arguments": '{"x":1}'}]
        self.assertEqual(normalize_tool_calls(raw_a), normalize_tool_calls(raw_b))

    def test_missing_tool_name_fails_closed(self):
        with self.assertRaises(ToolCallParseError):
            normalize_tool_call({"arguments": "{}"})

    def test_missing_arguments_fails_closed(self):
        with self.assertRaises(ToolCallParseError):
            normalize_tool_call({"name": "f"})

    def test_invalid_arguments_json_fails_closed(self):
        with self.assertRaises(ToolCallParseError):
            normalize_tool_call({"name": "f", "arguments": "{not json"})

    def test_one_call_no_tool_calls_field_is_valid_no_call_outcome(self):
        # The exact shape a model declining to call any tool returns:
        # no content, no tool_calls field at all. This is a structurally
        # valid response and must be a counted, non-error sample, not an
        # excluded one: excluding it is exactly the survivorship bias that
        # would let a sometimes-calling model look perfectly reproducible.
        provider = FakeProvider(result={
            "text": "", "tool_calls": None, "fingerprint": None, "model_version": "m",
        })
        rec = one_call(provider, TOOL_CASE, "burst")
        self.assertNotIn("error", rec)
        self.assertEqual(rec["tool_call_outcome"], "no_call")
        self.assertNotIn("tool_calls_normalized", rec)

    def test_one_call_empty_tool_calls_list_is_valid_no_call_outcome(self):
        provider = FakeProvider(result={
            "text": "", "tool_calls": [], "fingerprint": None, "model_version": "m",
        })
        rec = one_call(provider, TOOL_CASE, "burst")
        self.assertNotIn("error", rec)
        self.assertEqual(rec["tool_call_outcome"], "no_call")

    def test_one_call_malformed_tool_call_records_error(self):
        provider = FakeProvider(result={
            "text": "", "tool_calls": [{"name": None, "arguments": "{}"}],
            "fingerprint": None, "model_version": "m",
        })
        rec = one_call(provider, TOOL_CASE, "burst")
        self.assertIn("error", rec)
        self.assertIn("malformed", rec["error"])
        self.assertNotIn("tool_call_outcome", rec)
        self.assertNotIn("tool_calls_normalized", rec)

    def test_one_call_invalid_arguments_json_records_error(self):
        provider = FakeProvider(result={
            "text": "", "tool_calls": [{"id": "c1", "name": "f", "arguments": "{not json"}],
            "fingerprint": None, "model_version": "m",
        })
        rec = one_call(provider, TOOL_CASE, "burst")
        self.assertIn("error", rec)
        self.assertNotIn("tool_call_outcome", rec)

    def test_one_call_success_records_outcome_normalized_and_raw(self):
        provider = FakeProvider(result={
            "text": "", "tool_calls": [{"id": "c1", "name": "get_weather",
                                        "arguments": '{"city":"Lyon"}'}],
            "fingerprint": "fp1", "model_version": "m",
        })
        rec = one_call(provider, TOOL_CASE, "burst")
        self.assertNotIn("error", rec)
        self.assertEqual(rec["tool_call_outcome"], "tool_call")
        self.assertEqual(rec["tool_calls_normalized"], [["get_weather", '{"city":"Lyon"}']])
        self.assertEqual(rec["tool_calls_raw"], [{"id": "c1", "name": "get_weather",
                                                   "arguments": '{"city":"Lyon"}'}])

    def test_one_call_unsupported_provider_is_not_no_call(self):
        # A provider that cannot support tool_call cases at all (request()
        # raises before any response exists) must remain an error sample,
        # never a "the model chose not to call" observation.
        provider = FakeProvider(exc=NotImplementedError("provider 'gemini' ..."))
        rec = one_call(provider, TOOL_CASE, "burst")
        self.assertIn("error", rec)
        self.assertNotIn("tool_call_outcome", rec)

    def test_one_call_transport_failure_is_not_no_call(self):
        provider = FakeProvider(exc=RuntimeError("HTTP 500: boom"))
        rec = one_call(provider, TOOL_CASE, "burst")
        self.assertIn("error", rec)
        self.assertNotIn("tool_call_outcome", rec)


# ---------------------------------------------------------------------------
# D. Anthropic style parsing
# ---------------------------------------------------------------------------

class TestAnthropicParsing(unittest.TestCase):
    def test_tool_use_blocks_extracted(self):
        p = AnthropicMessages({"provider": "anthropic", "model": "m"})
        body = {
            "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "get_weather",
                 "input": {"city": "Lyon"}},
            ],
            "model": "claude-test",
        }
        parsed = p.parse(body)
        self.assertEqual(parsed["tool_calls"],
                         [{"name": "get_weather", "arguments": {"city": "Lyon"}, "id": "toolu_1"}])

    def test_non_tool_blocks_are_not_fake_calls(self):
        p = AnthropicMessages({"provider": "anthropic", "model": "m"})
        body = {"content": [{"type": "text", "text": "hello"}], "model": "m"}
        parsed = p.parse(body)
        self.assertIsNone(parsed["tool_calls"])
        self.assertEqual(parsed["text"], "hello")

    def test_text_only_response_is_valid_no_call_outcome(self):
        provider = FakeProvider(result={
            "text": "I do not have access to that.", "tool_calls": None,
            "fingerprint": None, "model_version": "claude-test",
        })
        rec = one_call(provider, TOOL_CASE, "burst")
        self.assertNotIn("error", rec)
        self.assertEqual(rec["tool_call_outcome"], "no_call")
        self.assertEqual(rec["text"], "I do not have access to that.")

    def test_returned_order_preserved(self):
        p = AnthropicMessages({"provider": "anthropic", "model": "m"})
        body = {"content": [
            {"type": "tool_use", "id": "1", "name": "a", "input": {}},
            {"type": "tool_use", "id": "2", "name": "b", "input": {}},
        ], "model": "m"}
        parsed = p.parse(body)
        self.assertEqual([c["name"] for c in parsed["tool_calls"]], ["a", "b"])

    def test_malformed_tool_use_block_fails_closed(self):
        with self.assertRaises(ToolCallParseError):
            normalize_tool_call({"name": None, "arguments": {"city": "Lyon"}})
        with self.assertRaises(ToolCallParseError):
            normalize_tool_call({"name": "f", "arguments": None})


# ---------------------------------------------------------------------------
# E. Canonical arguments and the NO_TOOL_CALL tag
# ---------------------------------------------------------------------------

class TestCanonicalArguments(unittest.TestCase):
    def test_key_order_normalizes_equally(self):
        a = normalize_arguments('{"a":1,"b":2}')
        b = normalize_arguments('{"b": 2, "a": 1}')
        self.assertEqual(a, b)

    def test_insignificant_whitespace_normalizes_equally(self):
        a = normalize_arguments('{"a":1}')
        b = normalize_arguments('{ "a" : 1 }')
        self.assertEqual(a, b)

    def test_different_values_remain_different(self):
        a = normalize_arguments('{"a":1}')
        b = normalize_arguments('{"a":2}')
        self.assertNotEqual(a, b)

    def test_array_order_significant(self):
        a = normalize_arguments('{"a":[1,2,3]}')
        b = normalize_arguments('{"a":[3,2,1]}')
        self.assertNotEqual(a, b)

    def test_nested_json_normalizes(self):
        a = normalize_arguments('{"outer":{"z":1,"a":2},"list":[{"y":1,"x":2}]}')
        b = normalize_arguments('{"list":[{"x":2,"y":1}],"outer":{"a":2,"z":1}}')
        self.assertEqual(a, b)

    def test_parsed_object_input_matches_string_input(self):
        obj_form = normalize_arguments({"b": 2, "a": 1})
        str_form = normalize_arguments('{"a": 1, "b": 2}')
        self.assertEqual(obj_form, str_form)

    def test_invalid_json_string_fails_closed(self):
        with self.assertRaises(ToolCallParseError):
            normalize_arguments("not json")

    def test_missing_arguments_fails_closed(self):
        with self.assertRaises(ToolCallParseError):
            normalize_arguments(None)

    def test_canonicalization_is_stable_across_repeated_application(self):
        samples = [
            '{"b":1,"a":[3,2,{"y":1,"x":0}],"c":null,"d":true}',
            '{}',
            '[1,2,3]',
            '{"nested":{"a":{"b":{"c":1}}}}',
        ]
        for s in samples:
            with self.subTest(s=s):
                once = normalize_arguments(s)
                twice = normalize_arguments(once)
                self.assertEqual(once, twice)

    def test_permuting_key_insertion_order_never_changes_canonical_form(self):
        import itertools
        base = {"alpha": 1, "beta": [1, 2], "gamma": {"x": True, "y": None}}
        keys = list(base.keys())
        forms = set()
        for perm in itertools.permutations(keys):
            obj = {k: base[k] for k in perm}
            forms.add(normalize_arguments(obj))
        self.assertEqual(len(forms), 1)

    def test_changing_transport_id_never_changes_semantic_normalization(self):
        rng_ids = ["call_1", "call_2", "abc-123", "0", ""]
        forms = set()
        for cid in rng_ids:
            raw = {"id": cid, "name": "f", "arguments": '{"a":1}'}
            forms.add(normalize_tool_call(raw))
        self.assertEqual(len(forms), 1)

    def test_changing_tool_name_always_changes_normalized_representation(self):
        names = ["a", "b", "get_weather", "get_Weather", "a_"]
        forms = {normalize_tool_call({"name": n, "arguments": "{}"}) for n in names}
        self.assertEqual(len(forms), len(names))

    def test_changing_one_argument_value_changes_normalized_representation(self):
        base = normalize_tool_call({"name": "f", "arguments": '{"x":1,"y":2}'})
        changed = normalize_tool_call({"name": "f", "arguments": '{"x":1,"y":3}'})
        self.assertNotEqual(base, changed)

    def test_reordering_calls_changes_normalized_representation(self):
        a = normalize_tool_calls([
            {"name": "f", "arguments": "{}"},
            {"name": "g", "arguments": "{}"},
        ])
        b = normalize_tool_calls([
            {"name": "g", "arguments": "{}"},
            {"name": "f", "arguments": "{}"},
        ])
        self.assertNotEqual(a, b)

    def test_no_raw_calls_normalizes_to_no_tool_call_tag(self):
        self.assertIs(normalize_tool_calls(None), NO_TOOL_CALL)
        self.assertIs(normalize_tool_calls([]), NO_TOOL_CALL)

    def test_no_tool_call_never_equals_any_tool_call_outcome(self):
        # Property: NO_TOOL_CALL != TOOL_CALL([...]) for any calls,
        # including a call list that normalizes to an empty tuple's
        # neighborhood (single call, many calls, degenerate arguments).
        outcomes = [
            normalize_tool_calls([{"name": "f", "arguments": "{}"}]),
            normalize_tool_calls([{"name": "a", "arguments": "{}"},
                                  {"name": "b", "arguments": "{}"}]),
            normalize_tool_calls([{"name": "f", "arguments": '{"x":null}'}]),
        ]
        for outcome in outcomes:
            with self.subTest(outcome=outcome):
                self.assertNotEqual(NO_TOOL_CALL, outcome)
                self.assertNotEqual(outcome, NO_TOOL_CALL)

    def test_no_tool_call_is_a_stable_singleton(self):
        self.assertEqual(normalize_tool_calls(None), normalize_tool_calls([]))
        self.assertEqual(hash(normalize_tool_calls(None)), hash(NO_TOOL_CALL))

    def test_malformed_non_empty_list_never_becomes_no_tool_call(self):
        with self.assertRaises(ToolCallParseError):
            normalize_tool_calls([{"name": None, "arguments": "{}"}])
        with self.assertRaises(ToolCallParseError):
            normalize_tool_calls([{"name": "f", "arguments": "not json"}])


# ---------------------------------------------------------------------------
# F. Scoring: call, no-call, malformed, and mixed behavior
# ---------------------------------------------------------------------------

def tool_call_sample(calls, **kw):
    return {"ts": "t", "mode": "burst", "text": "",
            "tool_call_outcome": "tool_call",
            "tool_calls_normalized": calls, **kw}


def no_call_sample(**kw):
    return {"ts": "t", "mode": "burst", "text": "no thanks",
            "tool_call_outcome": "no_call", **kw}


def error_sample(msg="malformed: tool call missing a name"):
    return {"ts": "t", "mode": "burst", "error": msg}


class TestToolCallScoring(unittest.TestCase):
    def test_identical_normalized_calls_score_identical(self):
        calls = [["get_weather", '{"city":"Lyon"}']]
        m = score_samples(
            [tool_call_sample(calls)] * 3, expect="tool_call")
        self.assertTrue(m["byte_identical"])
        self.assertEqual(m["distinct"], 1)
        self.assertEqual(m["mode_share"], 1.0)
        self.assertEqual(m["n_ok"], 3)
        self.assertEqual(m["tool_call_rate"], 1.0)

    def test_different_tool_names_diverge(self):
        m = score_samples([
            tool_call_sample([["get_weather", "{}"]]),
            tool_call_sample([["get_time", "{}"]]),
        ], expect="tool_call")
        self.assertFalse(m["byte_identical"])
        self.assertEqual(m["distinct"], 2)

    def test_different_arguments_diverge(self):
        m = score_samples([
            tool_call_sample([["f", '{"x":1}']]),
            tool_call_sample([["f", '{"x":2}']]),
        ], expect="tool_call")
        self.assertEqual(m["distinct"], 2)

    def test_different_call_order_diverges(self):
        m = score_samples([
            tool_call_sample([["a", "{}"], ["b", "{}"]]),
            tool_call_sample([["b", "{}"], ["a", "{}"]]),
        ], expect="tool_call")
        self.assertEqual(m["distinct"], 2)
        self.assertFalse(m["byte_identical"])

    def test_transport_ids_alone_do_not_diverge(self):
        calls = [["f", '{"x":1}']]
        m = score_samples([
            tool_call_sample(calls, tool_calls_raw=[{"id": "call_1", "name": "f",
                                                      "arguments": '{"x":1}'}]),
            tool_call_sample(calls, tool_calls_raw=[{"id": "call_2", "name": "f",
                                                      "arguments": '{"x":1}'}]),
        ], expect="tool_call")
        self.assertTrue(m["byte_identical"])

    # -- The core correction: call-decision divergence must not disappear --

    def test_half_call_half_no_call_cannot_score_as_perfect(self):
        calls = [["search", '{"q":"x"}']]
        samples = [tool_call_sample(calls) for _ in range(5)] + \
                  [no_call_sample() for _ in range(5)]
        m = score_samples(samples, expect="tool_call")
        # The bug this corrects: excluding no-call responses would leave
        # n_ok == 5, distinct == 1, byte_identical == True, mode_share == 1.0.
        self.assertEqual(m["n_ok"], 10)
        self.assertEqual(m["distinct"], 2)
        self.assertFalse(m["byte_identical"])
        self.assertEqual(m["mode_share"], 0.5)
        self.assertEqual(m["tool_call_rate"], 0.5)

    def test_repeated_no_call_counts_toward_n_ok(self):
        m = score_samples([no_call_sample(), no_call_sample(), no_call_sample()],
                          expect="tool_call")
        self.assertEqual(m["n_ok"], 3)
        self.assertEqual(m["errors"], 0)
        self.assertEqual(m["tool_call_rate"], 0.0)

    def test_repeated_no_call_omits_payload_specific_metrics(self):
        # All valid samples declined to call: there is no payload to claim
        # is reproducible. distinct / byte_identical / mode_share must be
        # left out, not published as a spurious "perfect" result.
        m = score_samples([no_call_sample()] * 4, expect="tool_call")
        self.assertNotIn("distinct", m)
        self.assertNotIn("byte_identical", m)
        self.assertNotIn("mode_share", m)
        self.assertEqual(m["tool_call_rate"], 0.0)

    def test_repeated_no_call_still_omitted_when_it_would_have_looked_identical(self):
        # Sanity check on the specific failure shape from the bug report:
        # even though every no_call sample is "the same" observation, we
        # never let that render as byte_identical == True for a tool_call
        # case, because that phrase would read as payload determinism.
        m = score_samples([no_call_sample()] * 2, expect="tool_call")
        self.assertNotIn("byte_identical", m)

    def test_malformed_is_not_no_call(self):
        samples = [error_sample(), error_sample(), no_call_sample()]
        m = score_samples(samples, expect="tool_call")
        self.assertEqual(m["n_ok"], 1)
        self.assertEqual(m["errors"], 2)
        self.assertEqual(m["tool_call_rate"], 0.0)

    def test_malformed_samples_do_not_increase_n_ok(self):
        samples = [
            tool_call_sample([["f", "{}"]]),
            error_sample("malformed: no tool calls present"),
            {"ts": "t", "mode": "burst", "text": ""},  # no outcome tag at all
        ]
        m = score_samples(samples, expect="tool_call")
        self.assertEqual(m["n_ok"], 1)
        self.assertEqual(m["errors"], 2)

    def test_all_malformed_cannot_become_no_call(self):
        m = score_samples([error_sample(), error_sample()], expect="tool_call")
        self.assertEqual(m["n_ok"], 0)
        self.assertNotIn("tool_call_rate", m)
        self.assertNotIn("byte_identical", m)

    def test_end_to_end_one_call_then_score_ignores_transport_id(self):
        provider_a = FakeProvider(result={
            "text": "", "tool_calls": [{"id": "call_1", "name": "f",
                                        "arguments": '{"x":1}'}],
            "fingerprint": None, "model_version": "m",
        })
        provider_b = FakeProvider(result={
            "text": "", "tool_calls": [{"id": "call_9", "name": "f",
                                        "arguments": '{"x":1}'}],
            "fingerprint": None, "model_version": "m",
        })
        rec_a = one_call(provider_a, TOOL_CASE, "burst")
        rec_b = one_call(provider_b, TOOL_CASE, "burst")
        m = score_samples([rec_a, rec_b], expect="tool_call")
        self.assertEqual(m["n_ok"], 2)
        self.assertTrue(m["byte_identical"])
        self.assertEqual(m["distinct"], 1)

    def test_end_to_end_half_call_half_decline(self):
        call_provider = FakeProvider(result={
            "text": "", "tool_calls": [{"id": "c1", "name": "search",
                                        "arguments": '{"q":"x"}'}],
            "fingerprint": None, "model_version": "m",
        })
        decline_provider = FakeProvider(result={
            "text": "I cannot help with that.", "tool_calls": None,
            "fingerprint": None, "model_version": "m",
        })
        recs = ([one_call(call_provider, TOOL_CASE, "burst") for _ in range(5)] +
                [one_call(decline_provider, TOOL_CASE, "burst") for _ in range(5)])
        m = score_samples(recs, expect="tool_call")
        self.assertEqual(m["n_ok"], 10)
        self.assertFalse(m["byte_identical"])
        self.assertEqual(m["tool_call_rate"], 0.5)

    def test_unsupported_samples_cannot_produce_perfect_score(self):
        samples = [
            error_sample("NotImplementedError: provider 'gemini' ..."),
            error_sample("NotImplementedError: provider 'gemini' ..."),
        ]
        m = score_samples(samples, expect="tool_call")
        self.assertEqual(m["n_ok"], 0)
        self.assertNotIn("byte_identical", m)
        self.assertNotIn("mode_share", m)
        self.assertNotIn("tool_call_rate", m)

    def test_first_divergence_char_and_json_metrics_absent(self):
        m = score_samples([tool_call_sample([["f", "{}"]])] * 2, expect="tool_call")
        self.assertNotIn("first_divergence_char", m)
        self.assertNotIn("json_parse_rate", m)
        self.assertNotIn("distinct_canonical_json", m)


# ---------------------------------------------------------------------------
# G. Unsupported-provider auditability and watch mode
# ---------------------------------------------------------------------------

class TestUnsupportedProviderAudit(unittest.TestCase):
    def test_skip_reason_persisted_in_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            cases_path = os.path.join(d, "cases.json")
            with open(cases_path, "w") as f:
                json.dump({"cases": [TOOL_CASE]}, f)
            config_path = os.path.join(d, "config.json")
            with open(config_path, "w") as f:
                json.dump({"targets": [
                    {"provider": "gemini", "model": "gemini-test"},
                ]}, f)
            out_dir = os.path.join(d, "runs")
            rc = cli_main(["run", "--config", config_path, "--cases", cases_path,
                          "--out", out_dir, "--burst", "0", "--serial", "0"])
            self.assertEqual(rc, 0)
            run_dirs = [os.path.join(out_dir, n) for n in os.listdir(out_dir)]
            self.assertEqual(len(run_dirs), 1)
            with open(os.path.join(run_dirs[0], "manifest.json")) as f:
                manifest = json.load(f)
            skipped = manifest["skipped_tool_call_cases"]
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0]["provider"], "gemini")
            self.assertEqual(skipped[0]["case"], "lookup-weather")
            self.assertIn("does not support", skipped[0]["reason"])
            # No probe file was written for the skipped tuple either.
            probes = os.listdir(os.path.join(run_dirs[0], "probes"))
            self.assertEqual(probes, [])


class TestWatchModeRejectsToolCalls(unittest.TestCase):
    def test_watch_tick_refuses_tool_call_case(self):
        with tempfile.TemporaryDirectory() as d:
            config_path = os.path.join(d, "config.json")
            cases_path = os.path.join(d, "cases.json")
            with open(config_path, "w") as f:
                json.dump({"targets": []}, f)
            with open(cases_path, "w") as f:
                json.dump({"cases": [TOOL_CASE]}, f)
            with self.assertRaises(SystemExit):
                run_tick(config_path, cases_path, watch_dir=os.path.join(d, "watch"))


if __name__ == "__main__":
    unittest.main()
