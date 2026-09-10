import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import daily_news_runner as runner


class EditorialCacheTests(unittest.TestCase):
    def test_same_slot_request_reuses_paid_result_across_instances(self):
        calls = []
        def generate(items, posted=(), pinned=''):
            calls.append(items)
            return {'stories': [{'headline': 'saved'}]}
        bot = SimpleNamespace(SYSTEM_PROMPT='policy', CLAUDE_MODEL='model', CANDIDATES=5)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            'NEWS_EDITORIAL_CACHE_DIR': root, 'SCHEDULE_SLOT_ID': 'slot-a'
        }):
            fn = runner.cached_news_editorial(bot, generate)
            result = fn([{'title': 'source'}], [])
            result['stories'][0]['headline'] = 'mutated by renderer'
            fresh = runner.cached_news_editorial(bot, generate)
            self.assertEqual(fresh([{'title': 'source'}], [])['stories'][0]['headline'], 'saved')
            self.assertEqual(len(calls), 1)
            fresh([{'title': 'updated source'}], [])
            fresh([{'title': 'source'}], ['already published'])
            bot.SYSTEM_PROMPT = 'new policy'
            fresh([{'title': 'source'}], [])
            os.environ['SCHEDULE_SLOT_ID'] = 'slot-b'
            fresh([{'title': 'source'}], [])
            self.assertEqual(len(calls), 5)

    def test_pinned_and_manual_calls_are_never_reused(self):
        calls = []
        def generate(*args):
            calls.append(args)
            return {'stories': [{'headline': 'saved'}]}
        bot = SimpleNamespace(SYSTEM_PROMPT='p', CLAUDE_MODEL='m', CANDIDATES=1)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            'NEWS_EDITORIAL_CACHE_DIR': root, 'SCHEDULE_SLOT_ID': ''
        }):
            fn = runner.cached_news_editorial(bot, generate)
            fn([], [])
            fn([], [])
            os.environ['SCHEDULE_SLOT_ID'] = 'slot'
            fn([], [], 'breaking')
            fn([], [], 'breaking')
            self.assertEqual(len(calls), 4)
