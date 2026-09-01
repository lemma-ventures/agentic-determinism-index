import json
import os
import tempfile
import unittest

from agentic_determinism_index.watch import (
    build_watch_drift,
    is_due,
    next_interval_s,
    schedule_next,
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


if __name__ == "__main__":
    unittest.main()
