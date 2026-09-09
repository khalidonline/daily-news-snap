import json
import sys
import types
import unittest
from datetime import datetime
from unittest.mock import patch

_fake_news_bot = types.ModuleType("news_bot")
_fake_news_bot.ANTHROPIC_API_KEY = "test-key"
_fake_news_bot.DRY_RUN = True
_fake_news_bot.commit_and_push = lambda *args, **kwargs: None
_fake_news_bot.ksa_stamp = lambda: "test-stamp"
_fake_news_bot.notify = lambda *args, **kwargs: None
sys.modules.setdefault("news_bot", _fake_news_bot)

import breaking_watch


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class TrustedVerificationTests(unittest.TestCase):
    def test_high_severity_gulf_candidate_is_detected(self):
        titles = [
            "Iran attacks 10 ships near Strait of Hormuz and a US-used base in Jordan - Reuters",
        ]
        self.assertTrue(breaking_watch._needs_trusted_verification(titles))

    def test_routine_market_candidate_does_not_force_trusted_verification(self):
        self.assertFalse(
            breaking_watch._needs_trusted_verification([
                "Saudi stocks edge lower as banking shares decline"
            ])
        )

    def test_classifier_forces_trusted_source_check_for_severe_candidate(self):
        body = json.dumps({
            "content": [{
                "type": "text",
                "text": (
                    '{"breaking": false, "event": "", "sources": [], '
                    '"official_source": false, "reason": "unverified"}'
                ),
            }],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }).encode("utf-8")
        with patch.object(
            breaking_watch.urllib.request,
            "urlopen",
            return_value=FakeResponse(body),
        ) as urlopen, patch.object(
            breaking_watch, "ANTHROPIC_API_KEY", "test-key"
        ):
            breaking_watch.classify(
                datetime(2026, 9, 9, 12, 0),
                ["Iran attacks ships near Strait of Hormuz - Reuters"],
            )

        payload = json.loads(urlopen.call_args.args[0].data)
        user_text = payload["messages"][0]["content"]
        self.assertIn("Reuters", user_text)
        self.assertIn("AP", user_text)
        self.assertIn("official", user_text.lower())
        self.assertIn("before rejecting", user_text.lower())
        self.assertEqual(payload["tools"][0]["max_uses"], 1)


if __name__ == "__main__":
    unittest.main()
