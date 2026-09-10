import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import daily_news_runner as runner


class EditorialCacheTests(unittest.TestCase):
    def test_editorially_rejected_result_is_not_retained(self):
        calls = []
        def generate(*args):
            calls.append(args)
            return {'stories': [{'item': 1, 'headline': 'no Snapchat score'}]}
        bot = SimpleNamespace(SYSTEM_PROMPT='p', CLAUDE_MODEL='m', CANDIDATES=1,
                              MAX_HEADLINES_TO_MODEL=1, summarize=generate)
        item = {'source': 'Example', 'title': 'New consumer technology', 'summary': '', 'link': 'https://example.com/a'}
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            'NEWS_EDITORIAL_CACHE_DIR': root, 'SCHEDULE_SLOT_ID': 'slot'
        }), patch.object(runner, 'balanced_shortlist', return_value=[item]), patch.object(runner, 'validate_ranked_result', side_effect=lambda result, shortlist: result):
            fn = runner.make_summarizer(bot)
            self.assertEqual(fn([item])['stories'], [])
            self.assertEqual(fn([item])['stories'], [])
            self.assertEqual(len(calls), 2)

    def test_cache_write_error_does_not_discard_paid_result(self):
        bot = SimpleNamespace(SYSTEM_PROMPT='p', CLAUDE_MODEL='m', CANDIDATES=1)
        result = {'stories': [{'headline': 'saved'}]}
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            'NEWS_EDITORIAL_CACHE_DIR': root, 'SCHEDULE_SLOT_ID': 'slot'
        }), patch('pathlib.Path.write_text', side_effect=OSError('disk full')):
            fn = runner.cached_news_editorial(bot, lambda *args: result)
            self.assertEqual(fn([]), result)

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
