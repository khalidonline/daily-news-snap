import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


_fake_news_bot = types.ModuleType("news_bot")
_fake_news_bot.ANTHROPIC_API_KEY = "test-key"
_fake_news_bot.DRY_RUN = True
_fake_news_bot.commit_and_push = lambda *args, **kwargs: None
_fake_news_bot.ksa_stamp = lambda: "test-stamp"
_fake_news_bot.notify = lambda *args, **kwargs: None
sys.modules.setdefault("news_bot", _fake_news_bot)

import breaking_watch


class BreakingWatchPersistentHeadlineMemoryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 29, 21, 0, tzinfo=timezone.utc)
        self.title = "Saudi Arabia announces new aviation rules affecting Riyadh flights"
        self.verdict = {
            "breaking": False,
            "event": "",
            "sources": ["Reuters", "BBC"],
            "official_source": False,
            "reason": "important but not a discrete breaking event",
        }

    def _seen_entry(self, title=None, hours_ago=0):
        title = title or self.title
        return {
            "key": breaking_watch._headline_key(title),
            "title": title,
            "at": (self.now - timedelta(hours=hours_ago)).isoformat(),
        }

    def test_recently_evaluated_headline_does_not_call_classifier_again(self):
        state = {"seen_titles": [self._seen_entry()]}
        with patch.object(breaking_watch, "ksa_now", return_value=self.now), \
                patch.object(breaking_watch, "load_state", return_value=state), \
                patch.object(
                    breaking_watch, "feed_fresh_items",
                    return_value=([self.title], True),
                ), \
                patch.object(
                    breaking_watch, "classify", return_value=self.verdict
                ) as classify, \
                patch.object(breaking_watch, "save_state") as save_state, \
                patch.object(breaking_watch, "notify"):
            breaking_watch._watch()
        classify.assert_not_called()
        save_state.assert_not_called()

    def test_publisher_suffix_change_does_not_rewake_classifier(self):
        state = {"seen_titles": [self._seen_entry()]}
        syndicated = self.title + " - Reuters"
        with patch.object(breaking_watch, "ksa_now", return_value=self.now), \
                patch.object(breaking_watch, "load_state", return_value=state), \
                patch.object(
                    breaking_watch, "feed_fresh_items",
                    return_value=([syndicated], True),
                ), \
                patch.object(
                    breaking_watch, "classify", return_value=self.verdict
                ) as classify, \
                patch.object(breaking_watch, "save_state"), \
                patch.object(breaking_watch, "notify"):
            breaking_watch._watch()
        classify.assert_not_called()

    def test_materially_changed_headline_is_evaluated(self):
        state = {"seen_titles": [self._seen_entry()]}
        changed = self.title + " after cabinet approval effective tomorrow"
        with patch.object(breaking_watch, "ksa_now", return_value=self.now), \
                patch.object(breaking_watch, "load_state", return_value=state), \
                patch.object(
                    breaking_watch, "feed_fresh_items",
                    return_value=([changed], True),
                ), \
                patch.object(
                    breaking_watch, "classify", return_value=self.verdict
                ) as classify, \
                patch.object(breaking_watch, "save_state"), \
                patch.object(breaking_watch, "notify"):
            breaking_watch._watch()
        classify.assert_called_once_with(self.now, [changed])

    def test_seen_memory_expires_after_one_day(self):
        state = {"seen_titles": [self._seen_entry(hours_ago=25)]}
        with patch.object(breaking_watch, "ksa_now", return_value=self.now), \
                patch.object(breaking_watch, "load_state", return_value=state), \
                patch.object(
                    breaking_watch, "feed_fresh_items",
                    return_value=([self.title], True),
                ), \
                patch.object(
                    breaking_watch, "classify", return_value=self.verdict
                ) as classify, \
                patch.object(breaking_watch, "save_state"), \
                patch.object(breaking_watch, "notify"):
            breaking_watch._watch()
        classify.assert_called_once_with(self.now, [self.title])

    def test_successful_nonbreaking_classification_persists_headline_memory(self):
        state = {"date": "2026-08-29", "posted": False, "stamps": []}
        with patch.object(breaking_watch, "ksa_now", return_value=self.now), \
                patch.object(breaking_watch, "load_state", return_value=state), \
                patch.object(
                    breaking_watch, "feed_fresh_items",
                    return_value=([self.title], True),
                ), \
                patch.object(
                    breaking_watch, "classify", return_value=self.verdict
                ), \
                patch.object(breaking_watch, "save_state") as save_state, \
                patch.object(breaking_watch, "notify"):
            breaking_watch._watch()
        save_state.assert_called_once()
        saved = save_state.call_args.args[0]
        self.assertEqual(saved["date"], "2026-08-29")
        self.assertFalse(saved["posted"])
        self.assertEqual(saved["stamps"], [])
        self.assertEqual(len(saved["seen_titles"]), 1)
        self.assertEqual(
            saved["seen_titles"][0]["key"],
            breaking_watch._headline_key(self.title),
        )

    def test_review_mode_can_persist_delivery_memory_when_enabled(self):
        state = {"date": "2026-08-29", "event_fp": "reviewed-event"}
        with tempfile.TemporaryDirectory() as td, \
                patch.object(breaking_watch, "STATE_FILE", Path(td) / "breaking.json"), \
                patch.object(breaking_watch, "DRY_RUN", True), \
                patch.object(
                    breaking_watch, "PERSIST_REVIEW_STATE", True, create=True
                ), \
                patch.object(breaking_watch, "commit_and_push") as commit:
            breaking_watch.save_state(state)

        commit.assert_called_once()
        self.assertEqual(commit.call_args.args[0].name, "breaking.json")

    def test_reviewed_card_uses_daily_cap_without_classifier(self):
        state = {
            "date": "2026-08-29",
            "posted": False,
            "reviewed": True,
            "stamps": ["test-stamp"],
        }
        with patch.object(breaking_watch, "ksa_now", return_value=self.now), \
                patch.object(breaking_watch, "load_state", return_value=state), \
                patch.object(breaking_watch, "feed_fresh_items") as feeds, \
                patch.object(breaking_watch, "classify") as classify, \
                patch.object(breaking_watch, "notify"):
            breaking_watch._watch()
        feeds.assert_not_called()
        classify.assert_not_called()

    def test_successful_review_marks_daily_cap(self):
        verdict = {
            "breaking": True,
            "event": "قرار سعودي عاجل مؤكد الآن",
            "sources": ["SPA", "Reuters"],
            "official_source": True,
            "reason": "confirmed",
        }
        saved = []
        with patch.object(breaking_watch, "ksa_now", return_value=self.now), \
                patch.object(breaking_watch, "load_state", return_value={}), \
                patch.object(
                    breaking_watch, "feed_fresh_items",
                    return_value=([self.title], True),
                ), \
                patch.object(breaking_watch, "classify", return_value=verdict), \
                patch.object(breaking_watch, "_run_news_bot", return_value=0), \
                patch.object(breaking_watch, "DRY_RUN", True), \
                patch.object(
                    breaking_watch, "PERSIST_REVIEW_STATE", True, create=True
                ), \
                patch.object(
                    breaking_watch, "save_state",
                    side_effect=lambda state: saved.append(dict(state)),
                ), \
                patch.object(breaking_watch, "notify"):
            breaking_watch._watch()

        self.assertTrue(saved[-1]["reviewed"])
        self.assertEqual(saved[-1]["stamps"], ["test-stamp"])
        self.assertEqual(saved[-1]["lock_at"], "")

    def test_classifier_failure_does_not_burn_headline(self):
        with patch.object(breaking_watch, "ksa_now", return_value=self.now), \
                patch.object(breaking_watch, "load_state", return_value={}), \
                patch.object(
                    breaking_watch, "feed_fresh_items",
                    return_value=([self.title], True),
                ), \
                patch.object(breaking_watch, "classify", return_value=None), \
                patch.object(breaking_watch, "save_state") as save_state, \
                patch.object(breaking_watch, "notify"):
            breaking_watch._watch()
        save_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
