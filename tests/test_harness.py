import json
import os
import tempfile
import unittest

from agentic_determinism_index.metrics import canonical_json, first_divergence, score_samples
from agentic_determinism_index.report import markdown, score_run
from agentic_determinism_index.site import aggregate_leaderboard, latest_scored_run, render_html


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
        ]

        leaders = aggregate_leaderboard(rows)
        self.assertEqual(len(leaders), 3)
        self.assertEqual(leaders[0]["provider"], "anthropic")
        self.assertEqual(leaders[0]["medal"], "1st")
        self.assertEqual(leaders[1]["provider"], "openai")
        self.assertEqual(leaders[1]["medal"], "2nd")

    def test_render_html(self):
        payload = {
            "title": "Determinism Index",
            "run_dir": "runs/reference/2026",
            "run_stamp": "2026",
            "generated_at": "2026-01-01T00:00:00Z",
            "started": "2026-01-01T00:00:00Z",
            "finished": "2026-01-01T00:01:00Z",
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
                    "models": [
                        {"name": "gpt", "rows": 4}
                    ],
                }
            ],
        }
        html = render_html(payload)
        self.assertIn("Determinism Index", html)
        self.assertIn("1st", html)
        self.assertIn("runs/reference/2026", html)
        self.assertIn("top3 medals", html.lower())


if __name__ == "__main__":
    unittest.main()
