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

    def test_one_miss_does_not_bench_a_tuple_for_a_month(self):
        import tempfile
        from agentic_determinism_index.watch import ingest_score_hints, load_watch_state

        cfg = {"non_exact_score_min_interval_s": 30 * 86400, "exact_score_min_interval_s": 86400}
        now = 1_000_000
        # A single non-exact run re-scores at the daily cadence...
        self.assertTrue(score_reprobe_due(
            {"byte_exact": False, "non_exact_streak": 1, "last_score_epoch": now - 90000}, now=now, cfg=cfg))
        # ...two in a row wait the long interval.
        self.assertFalse(score_reprobe_due(
            {"byte_exact": False, "non_exact_streak": 2, "last_score_epoch": now - 90000}, now=now, cfg=cfg))

        key = "openrouter|m|cerebras"
        with tempfile.TemporaryDirectory() as d:
            def score(stamp, *exact):
                ingest_score_hints(d, [
                    {"provider": "openrouter", "model": "m", "label": "cerebras", "case": f"c{i}", "byte_identical": e}
                    for i, e in enumerate(exact)
                ], run_stamp=stamp)
                return load_watch_state(d)["targets"][key]

            row = score("t1", True, False)
            self.assertEqual((row["byte_exact"], row["non_exact_streak"]), (False, 1))
            row = score("t2", False, True)
            self.assertEqual((row["byte_exact"], row["non_exact_streak"]), (False, 2))
            # A clean run clears an earlier miss (it used to stick forever).
            row = score("t3", True, True)
            self.assertEqual((row["byte_exact"], row["non_exact_streak"]), (True, 0))

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


class TestFailedScores(unittest.TestCase):
    """A score run where every request failed must not count as a score."""

    KEY = "openrouter|m|L"

    def _ingest(self, d, n_ok, stamp):
        from agentic_determinism_index.watch import ingest_score_hints, load_watch_state
        rows = [{"provider": "openrouter", "model": "m", "label": "L", "case": c,
                 "n": 10, "n_ok": n_ok, "errors": 10 - n_ok,
                 **({"mode_share": 0.5, "byte_identical": False} if n_ok else {})}
                for c in ("c1", "c2")]
        ingest_score_hints(d, rows, run_stamp=stamp)
        return load_watch_state(d)["targets"][self.KEY]

    def test_zero_ok_run_keeps_last_score_and_is_retried(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            good = self._ingest(d, 10, "2026-10-05T201706Z")
            good = self._ingest(d, 10, "2026-10-06T201706Z")
            last_epoch = good["last_score_epoch"]
            self.assertEqual(good["non_exact_streak"], 2)

            row = self._ingest(d, 0, "2026-10-25T181705Z")
            self.assertEqual(row["last_score_stamp"], "2026-10-06T201706Z")
            self.assertEqual(row["last_score_epoch"], last_epoch)
            self.assertEqual(row["last_score_attempt_stamp"], "2026-10-25T181705Z")
            self.assertEqual(row["score_failures"], 1)
            self.assertEqual(row["non_exact_streak"], 2, "a failed run is no verdict")

            cfg = {"failed_score_retry_s": 3600}
            now = row["last_score_attempt_epoch"]
            # Not hammered on the next tick, retried after the retry gap,
            # not after the month a measured non-exact stack waits.
            self.assertFalse(score_reprobe_due(row, now=now + 60, cfg=cfg))
            self.assertTrue(score_reprobe_due(row, now=now + 3601, cfg=cfg))

            row = self._ingest(d, 0, "2026-10-26T181705Z")
            self.assertEqual(row["score_failures"], 2)
            row = self._ingest(d, 7, "2026-10-27T181705Z")
            self.assertEqual(row["score_failures"], 0)
            self.assertEqual(row["last_score_stamp"], "2026-10-27T181705Z")
            self.assertGreaterEqual(row["last_score_epoch"], time.time() - 60)

    def test_force_rescore_before_makes_older_scores_due_once(self):
        from agentic_determinism_index.watch import parse_force_before
        force = parse_force_before("2026-10-26T10:00:00Z")
        import datetime
        self.assertEqual(force, datetime.datetime(
            2026, 10, 26, 10, tzinfo=datetime.timezone.utc).timestamp())
        cfg = {"non_exact_score_min_interval_s": 30 * 86400}
        old = {"byte_exact": False, "non_exact_streak": 2, "last_score_epoch": force - 9 * 86400}
        self.assertFalse(score_reprobe_due(old, now=force + 600, cfg=cfg))
        self.assertTrue(score_reprobe_due(old, now=force + 600, cfg=cfg, force_before=force))
        fresh = {**old, "last_score_epoch": force + 300}
        self.assertFalse(score_reprobe_due(fresh, now=force + 600, cfg=cfg, force_before=force))

    def test_parked_targets_are_never_due(self):
        from agentic_determinism_index.watch import filter_score_due_targets
        with tempfile.TemporaryDirectory() as d:
            due, skipped = filter_score_due_targets([
                {"provider": "openrouter", "model": "m", "label": "live"},
                {"provider": "openrouter", "model": "m", "label": "gone",
                 "parked_reason": "endpoint withdrawn"},
            ], d)
        self.assertEqual([t["label"] for t in due], ["live"])
        self.assertEqual(skipped[0]["reason"], "parked")

    def test_reasoning_targets_get_a_larger_watch_budget_only(self):
        from agentic_determinism_index.watch import watch_case_for
        case = {"id": "stack-ping", "params": {"temperature": 0, "seed": 42, "max_tokens": 8}}
        self.assertIs(watch_case_for(case, {"model": "m"}), case)
        bumped = watch_case_for(case, {"model": "m", "watch_max_tokens": 512})
        self.assertEqual(bumped["params"], {"temperature": 0, "seed": 42, "max_tokens": 512})
        self.assertEqual(case["params"]["max_tokens"], 8, "the shared case is not mutated")


class TestRunCommand(unittest.TestCase):
    def test_nothing_runnable_writes_no_run_directory(self):
        from agentic_determinism_index.cli import main
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "cfg.json")
            with open(cfg, "w") as f:
                json.dump({"targets": [
                    {"provider": "openai_compatible", "model": "m", "label": "keyless",
                     "api_key_env": "ADI_TEST_KEY_THAT_IS_NOT_SET"},
                    {"provider": "openrouter", "model": "m", "label": "parked",
                     "parked_reason": "endpoint withdrawn"},
                ]}, f)
            out = os.path.join(d, "runs")
            os.environ.pop("ADI_TEST_KEY_THAT_IS_NOT_SET", None)
            rc = main(["run", "--config", cfg, "--out", out, "--due-only",
                       "--watch-dir", os.path.join(d, "watch")])
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(out) and os.listdir(out))

    def test_score_of_an_all_failed_run_exits_3(self):
        from agentic_determinism_index.cli import main
        with tempfile.TemporaryDirectory() as d:
            run = os.path.join(d, "2026-10-25T181705Z")
            os.makedirs(os.path.join(run, "probes"))
            with open(os.path.join(run, "probes", "p.json"), "w") as f:
                json.dump({"target": {"provider": "openrouter", "model": "m", "label": "L"},
                           "case": {"id": "c", "expect": "text"},
                           "samples": [{"error": "RuntimeError: HTTP 404"}] * 3}, f)
            watch_dir = os.path.join(d, "watch")
            self.assertEqual(main(["score", run, "--watch-dir", watch_dir]), 3)
            with open(os.path.join(watch_dir, "state.json")) as f:
                row = json.load(f)["targets"]["openrouter|m|L"]
            self.assertNotIn("last_score_epoch", row)
            self.assertEqual(row["score_failures"], 1)


class TestReasoningEmptyCompletion(unittest.TestCase):
    def test_budget_spent_on_reasoning_is_named(self):
        from agentic_determinism_index.probe import one_call
        from agentic_determinism_index.providers import OpenAIChat

        class Fake(OpenAIChat):
            def call(self, case, timeout=180):
                return self.parse({"model": "m", "choices": [{
                    "finish_reason": "length",
                    "message": {"content": None, "reasoning": "The user says"}}]})

        rec = one_call(Fake({"model": "m"}), {"id": "c", "messages": []}, "watch")
        self.assertIn("max_tokens spent on reasoning", rec["error"])

    def test_account_ids_are_redacted_from_errors(self):
        from agentic_determinism_index.providers import redact_error_detail
        body = '{"error":{"code":404},"user_id":"user_abc123"}'
        self.assertEqual(redact_error_detail(body), '{"error":{"code":404},"user_id":"<redacted>"}')


if __name__ == "__main__":
    unittest.main()
