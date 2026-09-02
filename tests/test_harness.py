import json
import os
import tempfile
import unittest

from agentic_determinism_index.metrics import canonical_json, first_divergence, score_samples
from agentic_determinism_index.report import markdown, score_run
from agentic_determinism_index.site import (
    aggregate_leaderboard,
    build_payload,
    build_stack_drift,
    latest_scored_run,
    render_html,
)


def sample(text, **kw):
    return {"ts": "2026-01-01T00:00:00+00:00", "mode": "burst", "text": text, **kw}


class TestMetrics(unittest.TestCase):
    def test_first_divergence(self):
        self.assertIsNone(first_divergence(["abc", "abc"]))
        self.assertEqual(first_divergence(["abcd", "abce"]), 3)
        self.assertEqual(first_divergence(["abc", "abcd"]), 3)  # strict prefix
        self.assertEqual(first_divergence(["x", "y"]), 0)

    def test_canonical_json(self):
        self.assertEqual(canonical_json('{"b": 1, "a": 2}'), '{"a":2,"b":1}')
        self.assertIsNone(canonical_json("not json"))

    def test_identical(self):
        m = score_samples([sample("same")] * 5)
        self.assertTrue(m["byte_identical"])
        self.assertEqual(m["distinct"], 1)
        self.assertEqual(m["mode_share"], 1.0)
        self.assertIsNone(m["first_divergence_char"])

    def test_divergent_with_errors(self):
        samples = [sample("aaa"), sample("aaa"), sample("aab"),
                   {"ts": "t", "mode": "burst", "error": "HTTP 500"}]
        m = score_samples(samples)
        self.assertEqual((m["n"], m["n_ok"], m["errors"]), (4, 3, 1))
        self.assertFalse(m["byte_identical"])
        self.assertEqual(m["distinct"], 2)
        self.assertEqual(m["mode_share"], round(2 / 3, 4))
        self.assertEqual(m["first_divergence_char"], 2)

    def test_json_semantic_agreement(self):
        # different bytes, same canonical JSON
        m = score_samples([sample('{"a": 1, "b": 2}'), sample('{"b":2,"a":1}')],
                          expect="json")
        self.assertFalse(m["byte_identical"])
        self.assertEqual(m["json_parse_rate"], 1.0)
        self.assertEqual(m["distinct_canonical_json"], 1)

    def test_all_errors(self):
        m = score_samples([{"ts": "t", "mode": "burst", "error": "boom"}])
        self.assertEqual(m["n_ok"], 0)
        self.assertNotIn("distinct", m)


class TestReport(unittest.TestCase):
    def test_score_run_and_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "probes"))
            probe = {
                "target": {"provider": "openai", "model": "m1"},
                "case": {"id": "c1", "expect": "text"},
                "samples": [sample("x"), sample("x"), sample("y")],
            }
            with open(os.path.join(d, "probes", "openai__m1__c1.json"), "w") as f:
                json.dump(probe, f)
            rows = score_run(d)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["model"], "m1")
            self.assertEqual(rows[0]["distinct"], 2)
            md = markdown(rows)
            self.assertIn("| openai | m1 | c1 |", md)


class TestSite(unittest.TestCase):
    def test_latest_scored_run(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "20260101", "probes"))
            os.makedirs(os.path.join(d, "20260201", "probes"))
            os.makedirs(os.path.join(d, "20260301"))

            with open(os.path.join(d, "20260101", "scores.json"), "w") as f:
                json.dump([], f)
            with open(os.path.join(d, "20260201", "scores.json"), "w") as f:
                json.dump([], f)

            latest = latest_scored_run(d)
            self.assertEqual(os.path.basename(latest), "20260201")

    def test_aggregate_leaderboard_and_medals(self):
        rows = [
            {"provider": "openai", "model": "gpt", "mode_share": 0.9,
             "byte_identical": True, "distinct": 1.0},
            {"provider": "openai", "model": "gpt", "mode_share": 0.6,
             "byte_identical": False, "distinct": 2.0},
            {"provider": "anthropic", "model": "claude", "mode_share": 0.8,
             "byte_identical": True, "distinct": 1.0},
            {"provider": "mistral", "model": "mixtral", "mode_share": 0.2,
             "byte_identical": False, "distinct": 3.0},
            # All-error probe must not appear as a zero-score medal row.
            {"provider": "nvidia_nim", "model": "eol", "n_ok": 0, "errors": 13},
        ]

        leaders = aggregate_leaderboard(rows)
        self.assertEqual(len(leaders), 3)
        self.assertEqual(leaders[0]["provider"], "anthropic")
        self.assertEqual(leaders[0]["medal"], "1st")
        self.assertEqual(leaders[1]["provider"], "openai")
        self.assertEqual(leaders[1]["medal"], "2nd")
        self.assertTrue(all(e["provider"] != "nvidia_nim" for e in leaders))

    def test_aggregate_leaderboard_splits_labels(self):
        rows = [
            {"provider": "openrouter", "model": "llama", "label": "via Groq",
             "mode_share": 1.0, "byte_identical": True, "distinct": 1.0},
            {"provider": "openrouter", "model": "llama", "label": "via DeepInfra",
             "mode_share": 0.5, "byte_identical": False, "distinct": 2.0},
        ]
        leaders = aggregate_leaderboard(rows)
        self.assertEqual(len(leaders), 2)
        self.assertEqual(leaders[0]["label"], "via Groq")
        self.assertEqual(leaders[1]["label"], "via DeepInfra")
        self.assertEqual(leaders[0]["deterministic_runs"], 1)
        self.assertEqual(leaders[0]["streak"], 1)
        self.assertEqual(leaders[1]["deterministic_runs"], 0)
        self.assertEqual(leaders[1]["streak"], 0)

    def test_tuple_deterministic_survival_across_runs(self):
        with tempfile.TemporaryDirectory() as d:
            for name, rows in (
                ("r1", [
                    {"provider": "openrouter", "model": "llama", "label": "via Groq",
                     "mode_share": 1.0, "byte_identical": True, "distinct": 1},
                    {"provider": "openrouter", "model": "gpt", "label": "via Azure",
                     "mode_share": 1.0, "byte_identical": True, "distinct": 1},
                ]),
                ("r2", [
                    {"provider": "openrouter", "model": "llama", "label": "via Groq",
                     "mode_share": 1.0, "byte_identical": True, "distinct": 1},
                    {"provider": "openrouter", "model": "gpt", "label": "via Azure",
                     "mode_share": 0.5, "byte_identical": False, "distinct": 2},
                ]),
                ("r3", [
                    {"provider": "openrouter", "model": "llama", "label": "via Groq",
                     "mode_share": 1.0, "byte_identical": True, "distinct": 1},
                ]),
            ):
                path = os.path.join(d, name)
                os.makedirs(path)
                with open(os.path.join(path, "scores.json"), "w") as f:
                    json.dump(rows, f)

            from agentic_determinism_index.site import tuple_deterministic_survival
            surv = tuple_deterministic_survival(d)
            groq = surv[("openrouter", "llama", "via Groq")]
            azure = surv[("openrouter", "gpt", "via Azure")]
            self.assertEqual(groq["deterministic_runs"], 3)
            self.assertEqual(groq["runs_seen"], 3)
            self.assertEqual(groq["streak"], 3)
            self.assertEqual(azure["deterministic_runs"], 1)
            self.assertEqual(azure["runs_seen"], 2)
            self.assertEqual(azure["streak"], 0)

    def test_render_html(self):
        payload = {
            "title": "Agentic Determinism Index (ADI)",
            "run_dir": "runs/reference/2026",
            "run_stamp": "2026",
            "run_id": "qert7m2kn4vw",
            "run_href": "r/qert7m2kn4vw/",
            "generated_at": "2026-01-01T00:00:00Z",
            "started": "2026-01-01T00:00:00Z",
            "finished": "2026-01-01T00:01:00Z",
            "n_runs": 2,
            "providers": 1,
            "models": 1,
            "cases": 1,
            "scored_tuples": 1,
            "leaders": [
                {
                    "rank": 1,
                    "medal": "1st",
                    "provider": "openai",
                    "score": 85.5,
                    "mean_mode_share": 0.9,
                    "exact_match_rate": 1.0,
                    "mean_distinct": 1.0,
                    "rows": 4,
                    "deterministic_runs": 2,
                    "runs_seen": 3,
                    "streak": 2,
                    "stack_id": "abcd1234wxyz",
                    "stack_href": "r/qert7m2kn4vw/#abcd1234wxyz",
                    "models": [
                        {"name": "gpt", "rows": 4}
                    ],
                }
            ],
        }
        html = render_html(payload)
        self.assertIn("Agentic Determinism Index (ADI)", html)
        self.assertIn("1st", html)
        self.assertIn("Last run", html)
        self.assertIn("byte-exact", html)
        self.assertIn("row-exact", html)
        self.assertIn("medals", html.lower())
        self.assertIn(">1</div><div class=\"label\">providers", html)
        self.assertIn(">1</div><div class=\"label\">scored tuples", html)
        self.assertNotIn("tagcloud", html)
        self.assertIn("r/qert7m2kn4vw/", html)
        self.assertIn("abcd…wxyz", html)
        self.assertIn("Deterministic runs", html)
        self.assertIn("2&nbsp;/&nbsp;3", html)
        self.assertIn("streak 2", html)


class TestStackDrift(unittest.TestCase):
    def test_build_stack_drift_from_multiple_runs(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "r1", "probes"))
            os.makedirs(os.path.join(d, "r2", "probes"))

            rows1 = [
                {"provider": "openai", "model": "gpt", "case": "c1",
                 "mode_share": 1.0, "fingerprints": ["fp_a"],
                 "model_versions": ["v1"], "n": 10, "n_ok": 10, "errors": 0},
            ]
            rows2 = [
                {"provider": "openai", "model": "gpt", "case": "c1",
                 "mode_share": 0.5, "fingerprints": ["fp_b"],
                 "model_versions": ["v2"], "n": 10, "n_ok": 9, "errors": 1},
            ]
            for name, rows in [("r1", rows1), ("r2", rows2)]:
                with open(os.path.join(d, name, "scores.json"), "w") as f:
                    json.dump(rows, f)

            drift = build_stack_drift(d)
            self.assertEqual(len(drift), 1)
            self.assertEqual(drift[0]["drift_count"], 1)

            payload = build_payload(os.path.join(d, "r2"), run_root=d)
            html = render_html(payload)
            self.assertIn("Stack-drift timeline", html)
            self.assertIn("fp_a", html)
            self.assertIn("fp_b", html)


if __name__ == "__main__":
    unittest.main()


class TestDescribeRequest(unittest.TestCase):
    def test_payload_recorded_and_credentials_redacted(self):
        import os
        from agentic_determinism_index.providers import make_provider
        os.environ["ADI_TEST_KEY"] = "sk-secret-value"
        try:
            p = make_provider({"provider": "openai", "model": "m",
                               "api_key_env": "ADI_TEST_KEY"})
            case = {"messages": [{"role": "user", "content": "hi"}],
                    "params": {"temperature": 0, "seed": 42, "max_tokens": 8}}
            d = p.describe_request(case)
            self.assertEqual(d["payload"]["temperature"], 0)
            self.assertEqual(d["payload"]["seed"], 42)
            self.assertNotIn("sk-secret-value", json.dumps(d))
        finally:
            del os.environ["ADI_TEST_KEY"]
