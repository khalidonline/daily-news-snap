import json
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import topic_bot


class TopicRecoveryHandoffTests(unittest.TestCase):
    def test_selected_topic_brief_is_saved_before_visual_search(self):
        brief = {
            "title": "عنوان محفوظ",
            "body": "تفاصيل الموضوع",
            "takeaway": "الخلاصة",
            "source_url": "https://example.com/source",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.object(topic_bot, "OUT_DIR", Path(tmp)):
            path = topic_bot.save_topic_recovery_handoff("الموضوع الأصلي", brief)
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(saved["topic"], "الموضوع الأصلي")
        self.assertEqual(saved["brief"], brief)

    def test_recoverable_visual_failure_does_not_notify_telegram(self):
        sender = Mock()
        with patch.object(topic_bot, "notify", sender):
            topic_bot.report_recoverable_topic_failure(
                "slot — no topic card: none had a usable photo"
            )
        sender.assert_not_called()

    def test_recovery_payload_reuses_exact_brief_without_research(self):
        brief = {
            "title": "العنوان نفسه",
            "body": "النص نفسه",
            "takeaway": "الخلاصة نفسها",
            "source_url": "https://example.com/source",
            "image_queries": ["exact subject"],
            "image_queries_ar": ["الموضوع نفسه"],
        }
        encoded = base64.b64encode(json.dumps({
            "topic": "الموضوع المختار",
            "brief": brief,
        }, ensure_ascii=False).encode("utf-8")).decode("ascii")
        recovered = topic_bot.load_topic_recovery_handoff(encoded)
        self.assertEqual(recovered, {"topic": "الموضوع المختار", "brief": brief})

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(topic_bot, "OUT_DIR", Path(tmp)), \
                patch.object(topic_bot, "research") as research, \
                patch.object(topic_bot, "fetch_local_photo", return_value=("hero.jpg", None)):
            actual, photo, _credit = topic_bot.build_card(
                recovered["topic"], recovered["brief"]
            )
        research.assert_not_called()
        self.assertEqual(actual, brief)
        self.assertEqual(photo, "hero.jpg")


if __name__ == "__main__":
    unittest.main()
