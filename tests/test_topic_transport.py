import http.client
import unittest
from types import SimpleNamespace

from topic_snapchat import research_with_validation


class TopicResearchTransportTests(unittest.TestCase):
    def test_incomplete_anthropic_body_is_retried(self):
        calls = []
        bot = SimpleNamespace(SYSTEM_PROMPT="base prompt")
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

        def original(topic):
            calls.append(topic)
            if len(calls) == 1:
                raise http.client.IncompleteRead(b"partial", 100000)
            return dict(brief)

        result = research_with_validation(bot, original, "موضوع اقتصادي")

        self.assertEqual(result["title"], brief["title"])
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
