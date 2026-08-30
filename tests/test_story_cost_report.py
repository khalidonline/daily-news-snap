import json
import tempfile
import unittest
from pathlib import Path

import story_cost_report as scr


class StoryCostReportTests(unittest.TestCase):
    def test_summary_counts_paid_cache_visual_only_cost_and_states(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            usage = root / "model_usage.jsonl"
            notifications = root / "notifications.jsonl"
            rows = [
                {"timestamp": "2026-08-30T01:00:00+00:00", "event": "model_result", "story": "A", "revision": "r1", "message_id": "msg1", "estimated_usd": 2.5, "mode": "auto"},
                {"timestamp": "2026-08-30T01:01:00+00:00", "event": "cache_hit", "story": "A", "revision": "r1", "mode": "auto"},
                {"timestamp": "2026-08-30T01:02:00+00:00", "event": "cache_hit", "story": "A", "revision": "r1", "mode": "visual_only"},
                {"timestamp": "2026-08-30T01:03:00+00:00", "event": "call_block", "story": "A", "revision": "r1", "mode": "auto"},
                {"timestamp": "2026-08-30T01:04:00+00:00", "event": "final_state", "story": "A", "revision": "r1", "status": "READY"},
                {"timestamp": "2026-08-30T02:00:00+00:00", "event": "model_result", "story": "B", "revision": "r2", "message_id": "msg2", "estimated_usd": 3.0, "mode": "auto"},
                {"timestamp": "2026-08-30T02:01:00+00:00", "event": "visual_only_block", "story": "B", "revision": "r2", "mode": "visual_only"},
                {"timestamp": "2026-08-30T02:02:00+00:00", "event": "final_state", "story": "B", "revision": "r2", "status": "BLOCKED"},
            ]
            usage.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            notifications.write_text(json.dumps({
                "timestamp": "2026-08-30T01:04:30+00:00", "event": "telegram_sent",
                "story": "A", "revision": "r1", "status": "READY", "deck_hash": "h1",
            }) + "\n", encoding="utf-8")

            report = scr.summarize(usage, notifications)
            self.assertEqual(2, report["stories"])
            self.assertEqual(2, report["paid_editorial_calls"])
            self.assertEqual(2, report["cache_hits"])
            self.assertEqual(2, report["visual_only_runs"])
            self.assertEqual(5.5, report["estimated_usd"])
            self.assertEqual(1, report["second_call_blocks"])
            self.assertEqual(1, report["ready"])
            self.assertEqual(0, report["review"])
            self.assertEqual(1, report["blocked"])

    def test_any_unpriced_paid_call_reports_unpriced(self):
        with tempfile.TemporaryDirectory() as td:
            usage = Path(td) / "usage.jsonl"
            usage.write_text(json.dumps({
                "timestamp": "2026-08-30T01:00:00+00:00", "event": "model_result",
                "story": "A", "revision": "r", "message_id": "msg", "estimated_usd": None,
            }) + "\n", encoding="utf-8")
            report = scr.summarize(usage, Path(td) / "missing.jsonl")
            self.assertEqual("unpriced", report["estimated_usd"])

    def test_last_limits_to_most_recent_unique_stories(self):
        with tempfile.TemporaryDirectory() as td:
            usage = Path(td) / "usage.jsonl"
            rows = [
                {"timestamp": "2026-08-30T01:00:00+00:00", "event": "model_result", "story": "A", "revision": "a", "message_id": "a"},
                {"timestamp": "2026-08-30T02:00:00+00:00", "event": "model_result", "story": "B", "revision": "b", "message_id": "b"},
                {"timestamp": "2026-08-30T03:00:00+00:00", "event": "model_result", "story": "C", "revision": "c", "message_id": "c"},
            ]
            usage.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            report = scr.summarize(usage, Path(td) / "missing.jsonl", last=2)
            self.assertEqual(2, report["stories"])
            self.assertEqual(2, report["paid_editorial_calls"])


if __name__ == "__main__":
    unittest.main()
