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
import breaking_watch_entry


class BreakingWatchNotificationTests(unittest.TestCase):
    def test_no_new_feed_items_stays_silent(self):
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        with patch.object(breaking_watch, "notify") as send:
            breaking_watch_entry._install_quiet_notifications()
            with patch.object(breaking_watch, "ksa_now", return_value=now), \
                    patch.object(breaking_watch, "load_state", return_value={}), \
                    patch.object(
                        breaking_watch, "feed_fresh_items", return_value=([], True)
                    ):
                breaking_watch._watch()
        send.assert_not_called()

    def test_breaking_false_stays_silent(self):
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        with patch.object(breaking_watch, "notify") as send:
            breaking_watch_entry._install_quiet_notifications()
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
                    patch.object(breaking_watch, "save_state"):
                breaking_watch._watch()
        send.assert_not_called()

    def test_classifier_failure_still_notifies(self):
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        with patch.object(breaking_watch, "notify") as send:
            breaking_watch_entry._install_quiet_notifications()
            with patch.object(breaking_watch, "ksa_now", return_value=now), \
                    patch.object(breaking_watch, "load_state", return_value={}), \
                    patch.object(
                        breaking_watch, "feed_fresh_items",
                        return_value=(["Saudi candidate"], True),
                    ), \
                    patch.object(breaking_watch, "classify", return_value=None):
                breaking_watch._watch()
        send.assert_called_once()
        self.assertIn("تعذّر التصنيف", send.call_args.args[0])

    def test_real_breaking_alert_is_forwarded(self):
        with patch.object(breaking_watch, "notify") as send:
            breaking_watch_entry._install_quiet_notifications()
            breaking_watch.notify("🚨 بطاقة عاجلة نُشرت تلقائياً")
        send.assert_called_once_with("🚨 بطاقة عاجلة نُشرت تلقائياً")


if __name__ == "__main__":
    unittest.main()
