import io
import json
import os
import tempfile
import unittest

from agentic_determinism_index.feed import build_feed, load_provider_prefs, write_feed, read_feed
from agentic_determinism_index.mcp import Server, serve


PAYLOAD = {
    "generated_at": "2026-09-17T06:00:00Z",
    "run_stamp": "2026-09-17T051707Z",
    "n_runs": 12,
    "leaders": [
        {"provider": "openrouter", "model": "openai/gpt-oss-120b", "label": "Cerebras via OpenRouter",
         "display": "Cerebras via OpenRouter", "rank": 1, "medal": "1st", "score": 98.0,
         "mean_mode_share": 1.0, "exact_match_rate": 1.0, "runs_seen": 10, "deterministic_runs": 10,
         "streak": 10, "score_as_of": "2026-09-16T231701Z"},
        {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct", "label": "Groq via OpenRouter",
         "display": "Groq via OpenRouter", "rank": 2, "medal": "2nd", "score": 90.0,
         "mean_mode_share": 0.95, "exact_match_rate": 0.75, "runs_seen": 4, "deterministic_runs": 3,
         "streak": 0, "score_as_of": "2026-09-04T171705Z"},
    ],
}


class TestFeed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        cfg = {"targets": [
            {"provider": "openrouter", "model": "openai/gpt-oss-120b", "label": "Cerebras via OpenRouter",
             "provider_prefs": {"order": ["cerebras"], "allow_fallbacks": False}},
            {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct", "label": "Groq via OpenRouter",
             "provider_prefs": {"order": ["groq"], "allow_fallbacks": False}},
        ]}
        with open(os.path.join(self.tmp, "watch.json"), "w") as f:
            json.dump(cfg, f)

    def test_feed_carries_green_flag_and_request_pins(self):
        prefs = load_provider_prefs(self.tmp)
        self.assertEqual(prefs[("openrouter", "openai/gpt-oss-120b", "Cerebras via OpenRouter")]["provider_prefs"]["order"], ["cerebras"])
        doc = build_feed(PAYLOAD, config_dir=self.tmp)
        self.assertEqual(doc["feed_version"], 1)
        self.assertEqual(doc["run_stamp"], "2026-09-17T051707Z")
        rows = doc["tuples"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["green"], "streak 10: latest scored appearance byte-exact")
        self.assertEqual(rows[0]["provider_prefs"], {"order": ["cerebras"], "allow_fallbacks": False})
        self.assertFalse(rows[1]["green"], "a broken streak is not green however good the mean")
        self.assertEqual(rows[1]["mean_mode_share"], 0.95)

    def test_feed_round_trips_through_a_file(self):
        out = os.path.join(self.tmp, "site", "leaderboard.json")
        write_feed(out, PAYLOAD, config_dir=self.tmp)
        doc = read_feed(out)
        self.assertEqual([r["model"] for r in doc["tuples"]], ["openai/gpt-oss-120b", "meta-llama/llama-3.1-8b-instruct"])


class TestMCP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.feed = os.path.join(self.tmp, "leaderboard.json")
        write_feed(self.feed, PAYLOAD, config_dir=None)

    def rpc(self, *messages):
        inp = io.StringIO("".join(json.dumps(m) + "\n" for m in messages))
        out = io.StringIO()
        serve(Server(source=self.feed), inp=inp, out=out)
        return [json.loads(l) for l in out.getvalue().splitlines() if l.strip()]

    def test_initialize_list_and_call(self):
        replies = self.rpc(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "adi_green", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "adi_tuple", "arguments": {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "nope", "arguments": {}}},
        )
        by_id = {r["id"]: r for r in replies}
        self.assertEqual(by_id[1]["result"]["serverInfo"]["name"], "agentic-determinism-index")
        self.assertEqual([t["name"] for t in by_id[2]["result"]["tools"]], ["adi_leaderboard", "adi_tuple", "adi_green"])
        green = json.loads(by_id[3]["result"]["content"][0]["text"])["rows"]
        self.assertEqual([r["model"] for r in green], ["openai/gpt-oss-120b"])
        rows = json.loads(by_id[4]["result"]["content"][0]["text"])["rows"]
        self.assertEqual(rows[0]["label"], "Groq via OpenRouter")
        self.assertIn("error", by_id[5])
        self.assertNotIn(None, by_id, "a notification gets no reply")


if __name__ == "__main__":
    unittest.main()
