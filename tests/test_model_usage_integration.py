import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import breaking_watch
import breaking_news_runner
import model_usage
import news_bot
import story_bot
import topic_bot


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class ModelUsageIntegrationTests(unittest.TestCase):
    def setUp(self):
        model_usage.reset_run_state()

    def tearDown(self):
        model_usage.reset_run_state()

    def _rows(self, path):
        return [json.loads(line) for line in Path(path).read_text().splitlines()]

    def test_news_editorial_response_is_metered(self):
        payload = {
            "id": "news-msg",
            "usage": {"input_tokens": 1000, "output_tokens": 100},
            "content": [{"type": "text", "text": '{"caption":"x","stories":[]}'}],
        }
        items = [{"source": "source", "title": "title", "summary": "summary"}]
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"MODEL_USAGE_PATH": str(Path(td) / "usage.jsonl")}
        ), patch.object(news_bot, "ANTHROPIC_API_KEY", "key"), patch.object(
            news_bot.urllib.request, "urlopen", return_value=FakeResponse(payload)
        ):
            news_bot.summarize(items)
            rows = self._rows(Path(td) / "usage.jsonl")

        self.assertEqual((rows[0]["bot"], rows[0]["purpose"]), ("news", "editorial"))

    def test_topic_research_response_is_metered(self):
        payload = {
            "id": "topic-msg",
            "usage": {
                "input_tokens": 2000,
                "output_tokens": 200,
                "server_tool_use": {"web_search_requests": 1},
            },
            "content": [{"type": "text", "text": "{}"}],
        }
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"MODEL_USAGE_PATH": str(Path(td) / "usage.jsonl")}
        ), patch.object(topic_bot, "ANTHROPIC_API_KEY", "key"), patch.object(
            topic_bot.urllib.request, "urlopen", return_value=FakeResponse(payload)
        ):
            topic_bot.research("topic")
            rows = self._rows(Path(td) / "usage.jsonl")

        self.assertEqual((rows[0]["bot"], rows[0]["purpose"]), ("topic", "research"))
        self.assertEqual(rows[0]["web_search_requests"], 1)

    def test_story_research_response_is_metered(self):
        payload = {
            "id": "story-msg",
            "usage": {
                "input_tokens": 100_000,
                "output_tokens": 10_000,
                "server_tool_use": {"web_search_requests": 6},
            },
            "content": [{"type": "text", "text": "{}"}],
        }
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"MODEL_USAGE_PATH": str(Path(td) / "usage.jsonl")}
        ), patch.object(story_bot, "ANTHROPIC_API_KEY", "key"), patch.object(
            story_bot.urllib.request, "urlopen", return_value=FakeResponse(payload)
        ):
            story_bot.research("story")
            rows = self._rows(Path(td) / "usage.jsonl")

        self.assertEqual((rows[0]["bot"], rows[0]["purpose"]), ("story", "research"))
        self.assertEqual(rows[0]["estimated_usd"], 0.81)

    def test_breaking_classifier_response_is_metered(self):
        payload = {
            "id": "breaking-msg",
            "usage": {"input_tokens": 500, "output_tokens": 50},
            "content": [
                {"type": "text", "text": '{"breaking":false,"reason":"routine"}'}
            ],
        }
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"MODEL_USAGE_PATH": str(Path(td) / "usage.jsonl")}
        ), patch.object(breaking_watch, "ANTHROPIC_API_KEY", "key"), patch.object(
            breaking_watch.urllib.request, "urlopen", return_value=FakeResponse(payload)
        ):
            breaking_watch.classify(datetime(2026, 9, 3, 12, 0), ["headline"])
            rows = self._rows(Path(td) / "usage.jsonl")

        self.assertEqual(
            (rows[0]["bot"], rows[0]["purpose"]), ("breaking", "classifier")
        )

    def test_breaking_malformed_paid_response_does_not_buy_a_second_answer(self):
        payload = {
            "id": "breaking-bad",
            "usage": {"input_tokens": 500, "output_tokens": 50},
            "content": [{"type": "text", "text": "not JSON"}],
        }
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"MODEL_USAGE_PATH": str(Path(td) / "usage.jsonl")}
        ), patch.object(breaking_watch, "ANTHROPIC_API_KEY", "key"), patch.object(
            breaking_watch.urllib.request,
            "urlopen",
            return_value=FakeResponse(payload),
        ) as urlopen, patch.object(breaking_watch.time, "sleep") as sleep:
            verdict = breaking_watch.classify(
                datetime(2026, 9, 3, 12, 0), ["headline"]
            )
            rows = self._rows(Path(td) / "usage.jsonl")

        self.assertIsNone(verdict)
        self.assertEqual(len(rows), 1)
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_photo_vision_response_is_metered(self):
        payload = {
            "id": "vision-msg",
            "usage": {"input_tokens": 300, "output_tokens": 10},
            "content": [{"type": "text", "text": "نعم\nصورة مناسبة"}],
        }
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "photo.jpg"
            Image.new("RGB", (20, 20), "blue").save(image)
            usage_path = Path(td) / "usage.jsonl"
            with patch.dict(os.environ, {"MODEL_USAGE_PATH": str(usage_path)}), \
                    patch.object(news_bot, "ANTHROPIC_API_KEY", "key"), \
                    patch.object(news_bot, "VISION_GATE", True), \
                    patch.object(news_bot.urllib.request, "urlopen", return_value=FakeResponse(payload)):
                news_bot._gate_cache.clear()
                self.assertEqual(news_bot.photo_shows(image, "context"), "yes")
            rows = self._rows(usage_path)

        self.assertEqual((rows[0]["bot"], rows[0]["purpose"]), ("shared", "vision_photo"))

    def test_photo_vision_gate_fails_closed_without_api_key(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "photo.jpg"
            Image.new("RGB", (20, 20), "blue").save(image)
            with patch.object(news_bot, "ANTHROPIC_API_KEY", ""), \
                    patch.object(news_bot, "VISION_GATE", True):
                news_bot._gate_cache.clear()
                self.assertEqual(news_bot.photo_shows(image, "context"), "no")

    def test_photo_vision_gate_fails_closed_when_api_is_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "photo.jpg"
            Image.new("RGB", (20, 20), "blue").save(image)
            with patch.object(news_bot, "ANTHROPIC_API_KEY", "key"), \
                    patch.object(news_bot, "VISION_GATE", True), \
                    patch.object(news_bot.urllib.request, "urlopen",
                                 side_effect=OSError("vision unavailable")):
                news_bot._gate_cache.clear()
                self.assertEqual(news_bot.photo_shows(image, "context"), "no")

    def test_photo_vision_ceiling_prevents_an_extra_paid_response(self):
        payload = {
            "id": "vision-msg",
            "usage": {"input_tokens": 300, "output_tokens": 10},
            "content": [{"type": "text", "text": "نعم\nصورة مناسبة"}],
        }
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "photo.jpg"
            Image.new("RGB", (20, 20), "blue").save(image)
            usage_path = Path(td) / "usage.jsonl"
            with patch.dict(
                os.environ, {"MODEL_USAGE_PATH": str(usage_path)}
            ), patch.object(
                news_bot, "ANTHROPIC_API_KEY", "key"
            ), patch.object(
                news_bot, "VISION_GATE", True
            ), patch.object(
                news_bot, "VISION_MAX_PAID_RESPONSES", 1, create=True
            ), patch.object(
                news_bot.urllib.request,
                "urlopen",
                return_value=FakeResponse(payload),
            ) as urlopen:
                news_bot._gate_cache.clear()
                self.assertEqual(news_bot.photo_shows(image, "first"), "yes")
                self.assertEqual(news_bot.photo_shows(image, "second"), "no")
            rows = self._rows(usage_path)

        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(len(rows), 1)

    def test_breaking_strict_vision_response_is_metered(self):
        payload = {
            "id": "strict-vision-msg",
            "usage": {"input_tokens": 300, "output_tokens": 10},
            "content": [{"type": "text", "text": "نعم\nصورة مرتبطة"}],
        }
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "photo.jpg"
            Image.new("RGB", (20, 20), "blue").save(image)
            usage_path = Path(td) / "usage.jsonl"
            with patch.dict(
                os.environ, {"MODEL_USAGE_PATH": str(usage_path)}
            ), patch.object(
                news_bot, "ANTHROPIC_API_KEY", "key"
            ), patch.object(
                breaking_news_runner.urllib.request,
                "urlopen",
                return_value=FakeResponse(payload),
            ):
                verdict = breaking_news_runner._strict_vision_verdict(
                    news_bot, image, "حدث عاجل"
                )
            rows = self._rows(usage_path)

        self.assertEqual(verdict, "yes")
        self.assertEqual(
            (rows[0]["bot"], rows[0]["purpose"]),
            ("breaking", "vision_strict"),
        )


if __name__ == "__main__":
    unittest.main()
