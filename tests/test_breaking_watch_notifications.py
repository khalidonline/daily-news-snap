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


class BreakingWatchNotificationTests(unittest.TestCase):
    def test_no_new_feed_items_stays_silent(self):
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        with patch.object(breaking_watch, "ksa_now", return_value=now), \
                patch.object(breaking_watch, "load_state", return_value={}), \
                patch.object(
                    breaking_watch, "feed_fresh_items", return_value=([], True)
                ), \
                patch.object(breaking_watch, "notify") as notify:
            breaking_watch._watch()
        notify.assert_not_called()

    def test_breaking_false_stays_silent(self):
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        with patch.object(breaking_watch, "ksa_now", return_value=now), \
                patch.object(breaking_watch, "load_state", return_value={}), \
                patch.object(
                    breaking_watch, "feed_fresh_items",
                    return_value=(["Saudi routine update"], True),
                ), \
                patch.object(
                    breaking_watch, "classify",
                    return_value={
                        "breaking": False,
                        "event": "",
                        "sources": [],
                        "official_source": False,
                        "reason": "routine",
                    },
                ), \
                patch.object(breaking_watch, "save_state"), \
                patch.object(breaking_watch, "notify") as notify:
            breaking_watch._watch()
        notify.assert_not_called()

    def test_classifier_failure_still_notifies(self):
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        with patch.object(breaking_watch, "ksa_now", return_value=now), \
                patch.object(breaking_watch, "load_state", return_value={}), \
                patch.object(
                    breaking_watch, "feed_fresh_items",
                    return_value=(["Saudi candidate"], True),
                ), \
                patch.object(breaking_watch, "classify", return_value=None), \
                patch.object(breaking_watch, "notify") as notify:
            breaking_watch._watch()
        notify.assert_called_once()
        self.assertIn("تعذّر التصنيف", notify.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
