import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

_fake_news_bot = types.ModuleType("news_bot")
_fake_news_bot.ANTHROPIC_API_KEY = "test-key"
_fake_news_bot.DRY_RUN = True
_fake_news_bot.commit_and_push = lambda *args, **kwargs: None
_fake_news_bot.ksa_stamp = lambda: "test-stamp"
_fake_news_bot.notify = lambda *args, **kwargs: None
sys.modules.setdefault("news_bot", _fake_news_bot)

import breaking_watch


class BreakingRecommendationTests(unittest.TestCase):
    def test_prompt_rejects_scheduled_arrival_or_routine_bilateral_meeting(self):
        prompt = breaking_watch.WATCH_PROMPT
        self.assertIn("وصولٌ أو بدء زيارة رسمية → ليست عاجلة", prompt)
        self.assertIn("لقاء ثنائي روتيني", prompt)
        self.assertIn("تطور جوهري غير متوقع", prompt)

    def test_same_event_fingerprint_is_filtered_before_classifier(self):
        now = datetime(2026, 9, 1, 17, 26, tzinfo=timezone.utc)
        event = "وصول السلطان هيثم إلى جدة ولقاؤه ولي العهد"
        state = {
            "date": now.date().isoformat(),
            "posted": False,
            "event_fp": breaking_watch.event_fp(event),
            "lock_at": "",
            "stamps": [],
            "seen_titles": [],
        }
        titles = [
            "السلطان هيثم يصل جدة ويلتقي ولي العهد",
            "خبر سعودي آخر يستحق التقييم",
        ]
        with patch.object(breaking_watch, "ksa_now", return_value=now), \
                patch.object(breaking_watch, "load_state", return_value=state), \
                patch.object(breaking_watch, "feed_fresh_items", return_value=(titles, True)), \
                patch.object(breaking_watch, "classify") as classify, \
                patch.object(breaking_watch, "notify"):
            breaking_watch._watch()

        sent_titles = classify.call_args.args[1]
        self.assertEqual(sent_titles, ["خبر سعودي آخر يستحق التقييم"])


if __name__ == "__main__":
    unittest.main()
