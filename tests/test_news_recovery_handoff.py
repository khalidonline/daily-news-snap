import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import daily_news_fresh_runner as runner


class RecoveryHandoffTests(unittest.TestCase):
    def test_recoverable_notice_does_not_call_sender(self):
        sender = Mock()
        bot = SimpleNamespace(notify=sender)
        runner.install_news_notification_labels(bot)
        bot.notify('⚠️ slot — no card: the model returned no stories')
        bot.notify('⚠️ slot — no card: visual recovery infrastructure failed')
        sender.assert_not_called()
        bot.notify('✅ Telegram delivery confirmed')
        sender.assert_called_once_with('✅ Telegram delivery confirmed')

    def test_selected_story_is_saved_before_visual_failure(self):
        story = {'headline': 'عنوان', 'summary': 'ملخص', 'visual_targets': []}
        result = {'stories': [story, {'headline': 'another'}]}
        with tempfile.TemporaryDirectory() as tmp:
            bot = SimpleNamespace(OUT_DIR=Path(tmp), summarize=Mock(return_value=result))
            runner.install_news_recovery_handoff(bot)
            self.assertIs(bot.summarize([], [], pinned=None), result)
            saved = json.loads((Path(tmp) / 'news_recovery_story.json').read_text())
            self.assertEqual(saved, story)
            bot.summarize.__wrapped__.assert_called_once_with([], [], pinned=None)

    def test_empty_result_removes_stale_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'news_recovery_story.json'
            path.write_text('{"headline":"old"}')
            bot = SimpleNamespace(OUT_DIR=Path(tmp), summarize=Mock(return_value={'stories': []}))
            runner.install_news_recovery_handoff(bot)
            bot.summarize([], [])
            self.assertFalse(path.exists())
