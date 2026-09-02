import json
import os
import tempfile
import unittest

from agentic_determinism_index.watch import (
    build_watch_drift,
    is_due,
    next_interval_s,
    schedule_next,
    score_reprobe_due,
)


class TestWatchSchedule(unittest.TestCase):
    def test_backoff_grows_after_stable_streak(self):
        base = next_interval_s({"stable_streak": 0}, {"min_interval_s": 100, "max_interval_s": 10000, "backoff": 2.0, "stable_after": 3})
        self.assertEqual(base, 100)
        grown = next_interval_s({"stable_streak": 5}, {"min_interval_s": 100, "max_interval_s": 10000, "backoff": 2.0, "stable_after": 3})
        self.assertGreater(grown, base)
        capped = next_interval_s({"stable_streak": 50}, {"min_interval_s": 100, "max_interval_s": 500, "backoff": 2.0, "stable_after": 3})
        self.assertEqual(capped, 500)

    def test_jitter_bounds(self):
        row = {"stable_streak": 0}
        cfg = {"min_interval_s": 1000, "max_interval_s": 1000, "backoff": 1.5, "stable_after": 3, "jitter": 0.2}

        class R:
            def uniform(self, a, b):
                return b  # max jitter

        due, interval = schedule_next(0, row, cfg, rng=R())
        self.assertEqual(interval, 1000)
        self.assertAlmostEqual(due, 1200.0)

    def test_is_due(self):
        self.assertTrue(is_due({}, now=100))
        self.assertTrue(is_due({"next_due_epoch": 50}, now=100))
        self.assertFalse(is_due({"next_due_epoch": 150}, now=100))

    def test_build_watch_drift(self):
        rows = [
            {"ts": "t1", "provider": "openai", "model": "m", "stack_id": "fp:a", "fingerprint": "a"},
            {"ts": "t2", "provider": "openai", "model": "m", "stack_id": "fp:a", "fingerprint": "a"},
            {"ts": "t3", "provider": "openai", "model": "m", "stack_id": "fp:b", "fingerprint": "b"},
        ]
        drift = build_watch_drift(rows)
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0]["drift_count"], 1)
        self.assertEqual(drift[0]["latest_stack_id"], "fp:b")

    def test_non_exact_backs_off_score_reprobe(self):
        now = 1_000_000
        # Just scored non-exact → not due (monthly cadence)
        self.assertFalse(score_reprobe_due(
            {"byte_exact": False, "last_score_epoch": now - 3600},
            now=now,
            cfg={"non_exact_score_min_interval_s": 30 * 86400, "exact_score_min_interval_s": 86400},
        ))
        # Non-exact after ~31 days → due
        self.assertTrue(score_reprobe_due(
            {"byte_exact": False, "last_score_epoch": now - 31 * 86400},
            now=now,
            cfg={"non_exact_score_min_interval_s": 30 * 86400, "exact_score_min_interval_s": 86400},
        ))
        # Byte-exact yesterday → due again after 1 day
        self.assertTrue(score_reprobe_due(
            {"byte_exact": True, "last_score_epoch": now - 90000},
            now=now,
            cfg={"non_exact_score_min_interval_s": 30 * 86400, "exact_score_min_interval_s": 86400},
        ))
        # Non-exact watch interval longer than exact baseline
        non_exact = next_interval_s(
            {"stable_streak": 0, "byte_exact": False},
            {
                "min_interval_s": 100,
                "max_interval_s": 10000,
                "non_exact_max_interval_s": 50000,
                "backoff": 1.5,
                "stable_after": 3,
            },
        )
        exact = next_interval_s(
            {"stable_streak": 0, "byte_exact": True},
            {
                "min_interval_s": 100,
                "max_interval_s": 10000,
                "non_exact_max_interval_s": 50000,
                "backoff": 1.5,
                "stable_after": 3,
            },
        )
        self.assertGreater(non_exact, exact)

    def test_filter_score_due_targets(self):
        import tempfile
        from agentic_determinism_index.watch import filter_score_due_targets, ingest_score_hints

        with tempfile.TemporaryDirectory() as d:
            ingest_score_hints(
                d,
                [
                    {
                        "provider": "openrouter",
                        "model": "m",
                        "label": "exact",
                        "byte_identical": True,
                    },
                    {
                        "provider": "openrouter",
                        "model": "m",
                        "label": "noisy",
                        "byte_identical": False,
                    },
                ],
                run_stamp="t0",
            )
            targets = [
                {"provider": "openrouter", "model": "m", "label": "exact"},
                {"provider": "openrouter", "model": "m", "label": "noisy"},
                {"provider": "openrouter", "model": "m", "label": "new"},
            ]
            due, skipped = filter_score_due_targets(
                targets,
                d,
                now=1_000_000,
                cfg={
                    "exact_score_min_interval_s": 86400,
                    "non_exact_score_min_interval_s": 30 * 86400,
                },
            )
            # All just scored / new: exact+noisy not due (just ingested), new is due
            labels = {t.get("label") for t in due}
            self.assertIn("new", labels)
            self.assertNotIn("exact", labels)
            self.assertNotIn("noisy", labels)
            self.assertEqual(len(skipped), 2)


if __name__ == "__main__":
    unittest.main()
