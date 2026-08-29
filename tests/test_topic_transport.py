import http.client
import json
import unittest
from unittest.mock import patch

import topic_bot


class _FakeResponse:
    def __init__(self, *, payload=None, error=None):
        self.payload = payload
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        if self.error is not None:
            raise self.error
        return self.payload


class TopicResearchTransportTests(unittest.TestCase):
    def test_incomplete_anthropic_body_is_retried(self):
        brief = {
            "title": "عنوان واضح",
            "body": "متن خبري واضح",
            "takeaway": "خلاصة خبرية",
            "caption": "تعليق خبري",
            "sources": ["واس", "Reuters"],
            "image_queries": ["Saudi economy", "Saudi business", "Saudi finance"],
            "image_queries_ar": ["اقتصاد سعودي", "أعمال سعودية", "تمويل سعودي"],
            "image_prompt": "high-quality editorial photograph about the Saudi economy",
            "source_url": "https://example.com/source",
        }
        claude_payload = {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": json.dumps(brief, ensure_ascii=False)}],
        }
        responses = [
            _FakeResponse(error=http.client.IncompleteRead(b"partial", 100000)),
            _FakeResponse(payload=json.dumps(claude_payload, ensure_ascii=False).encode()),
        ]

        with patch.object(topic_bot, "ANTHROPIC_API_KEY", "test-key"), \
                patch.object(topic_bot, "load_voice", return_value=[]), \
                patch.object(topic_bot.urllib.request, "urlopen", side_effect=responses) as urlopen, \
                patch("time.sleep", return_value=None):
            result = topic_bot.research("موضوع اقتصادي")

        self.assertEqual(result["title"], brief["title"])
        self.assertEqual(urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
