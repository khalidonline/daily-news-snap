import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import news_bot_core as bot
import story_cost_guard as scg


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({
            "id": "vision_1",
            "usage": {"input_tokens": 300, "output_tokens": 10},
            "content": [{"type": "text", "text": "نعم\nصورة مناسبة"}],
        }).encode("utf-8")


class StoryAuxUsageIntegrationTests(unittest.TestCase):
    def setUp(self):
        scg.reset_aux_run_state()

    def tearDown(self):
        scg.reset_aux_run_state()

    def test_story_photo_vision_is_written_to_story_cost_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "photo.jpg"
            Image.new("RGB", (20, 20), "blue").save(image)
            with patch.dict(os.environ, {
                "STORY_COST_STATE_ROOT": td,
                "STORY_USAGE_CONTEXT": "قصة اختبار",
            }), patch.object(bot, "ANTHROPIC_API_KEY", "key"), patch.object(
                bot, "VISION_GATE", True
            ), patch.object(
                bot.urllib.request, "urlopen", return_value=FakeResponse()
            ):
                bot._gate_cache.clear()
                self.assertEqual("yes", bot.photo_shows(image, "context"))
                ledger = scg.usage_ledger_path()
            rows = [
                json.loads(line)
                for line in ledger.read_text().splitlines()
            ]

        self.assertEqual(1, len(rows))
        self.assertEqual("aux_model_result", rows[0]["event"])
        self.assertEqual("vision_photo", rows[0]["purpose"])


if __name__ == "__main__":
    unittest.main()
