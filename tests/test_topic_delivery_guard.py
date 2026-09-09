import base64
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import topic_delivery_guard as guard


class TopicDeliveryGuardTests(unittest.TestCase):
    def payload(self, topic):
        raw = json.dumps({"topic": topic, "brief": {"title": "same card"}},
                         ensure_ascii=False).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    def test_confirmed_topic_blocks_exact_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "deliveries.json"
            env = root / "github_env"
            state.write_text(json.dumps([{
                "topic": "الطاقة المتجددة",
                "at": "2026-09-09T06:02:00+00:00",
            }], ensure_ascii=False), encoding="utf-8")

            duplicate = guard.check_recovery(
                self.payload("الطاقة المتجددة"), state, env,
                now=datetime(2026, 9, 9, 17, 0, tzinfo=timezone.utc),
            )

            self.assertTrue(duplicate)
            values = env.read_text(encoding="utf-8")
            self.assertIn("RECOVERY_ALREADY_DELIVERED=1", values)
            self.assertIn("RUN_SCHEDULED_BOT=0", values)

    def test_unconfirmed_topic_allows_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "deliveries.json"
            env = root / "github_env"
            duplicate = guard.check_recovery(
                self.payload("موضوع لم يصل"), state, env,
                now=datetime(2026, 9, 9, 17, 0, tzinfo=timezone.utc),
            )
            self.assertFalse(duplicate)
            self.assertEqual(env.read_text(encoding="utf-8"),
                             "RECOVERY_ALREADY_DELIVERED=0\n")

    def test_record_latest_uses_separate_confirmed_delivery_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            used = root / "topics_used.json"
            state = root / "deliveries.json"
            used.write_text(json.dumps([
                {"topic": "قديم", "at": "2026-09-08T06:00:00"},
                {"topic": "الجديد", "at": "2026-09-09T06:00:00"},
            ], ensure_ascii=False), encoding="utf-8")
            guard.record_latest(
                used, state,
                now=datetime(2026, 9, 9, 6, 2, tzinfo=timezone.utc),
            )
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(saved, [{
                "topic": "الجديد",
                "at": "2026-09-09T06:02:00+00:00",
            }])


if __name__ == "__main__":
    unittest.main()
