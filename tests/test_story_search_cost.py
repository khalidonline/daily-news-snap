import contextlib
import io
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import story_bot as sb
import story_editorial_runtime as runtime
from tests.test_story_editorial_runtime import good_brief


class StorySearchCostTests(unittest.TestCase):
    def run_research(self, version=None):
        # Other integration suites configure the shared story_bot module at
        # import time. Load an isolated instance to exercise fresh research.
        spec = importlib.util.spec_from_file_location(
            'story_bot_search_test', Path(sb.__file__)
        )
        bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bot)
        payloads = []
        response = {
            'id': 'search-test', 'stop_reason': 'end_turn',
            'usage': {'input_tokens': 1200, 'output_tokens': 500,
                      'server_tool_use': {'web_search_requests': 3}},
            # Filtered results can omit the raw search blocks. Code execution
            # is not an extra web search and must not confuse the JSON reader.
            'content': [
                {'type': 'server_tool_use', 'name': 'bash_code_execution',
                 'input': {'command': 'filter results'}},
                {'type': 'bash_code_execution_tool_result', 'content': {}},
                {'type': 'text', 'text': json.dumps(good_brief())},
            ],
        }

        def urlopen(request, **kwargs):
            payloads.append(json.loads(request.data))
            return io.BytesIO(json.dumps(response).encode())

        env = {} if version is None else {'STORY_WEB_SEARCH_TYPE': version}
        output = io.StringIO()
        with patch.dict(os.environ, env, clear=True), \
                patch.object(bot, 'ANTHROPIC_API_KEY', 'test-only'), \
                patch.object(bot.urllib.request, 'urlopen', urlopen), \
                contextlib.redirect_stdout(output):
            brief = runtime._research_with_paid_response_ceiling(bot, bot.research, 'test story')
        return payloads, brief, output.getvalue(), bot._LAST_EDITORIAL_USAGE

    def test_filtered_research_preserves_brief_and_usage_in_one_response(self):
        payloads, brief, output, usage = self.run_research()
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]['tools'], [{
            'type': 'web_search_20260318', 'name': 'web_search',
            'max_uses': sb.MAX_SEARCHES, 'response_inclusion': 'excluded',
        }])
        self.assertEqual(brief, good_brief())
        self.assertEqual(usage['web_search_requests'], 3)
        self.assertIn('3 web searches used', output)

    def test_explicit_legacy_rollback_omits_unsupported_parameter(self):
        payloads, brief, _, _ = self.run_research('web_search_20250305')
        self.assertEqual(payloads[0]['tools'], [{
            'type': 'web_search_20250305', 'name': 'web_search',
            'max_uses': sb.MAX_SEARCHES,
        }])
        self.assertEqual(brief, good_brief())

    def test_invalid_tool_version_stops_before_network(self):
        with self.assertRaises(ValueError):
            self.run_research('not-a-tool')
