import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import story_bot


class StoryArchivalVisualTests(unittest.TestCase):
    def _find_neutral_commons(self, title, context):
        with tempfile.TemporaryDirectory() as raw:
            out_path = Path(raw) / "frame.jpg"
            bank = []

            def commons(_queries, candidate, **_kwargs):
                candidate = Path(candidate)
                candidate.write_bytes(b"commons-photo")
                Path(str(candidate) + ".commons-title").write_text(
                    title, encoding="utf-8"
                )
                return str(candidate), "Wikimedia Commons"

            with patch.object(
                story_bot, "fetch_local_photo", return_value=(None, None)
            ), patch.object(
                story_bot, "fetch_spa_photo", return_value=(None, None)
            ), patch.object(
                story_bot, "fetch_commons_photo", side_effect=commons
            ), patch.object(
                story_bot, "fetch_loc_photo", return_value=(None, None)
            ), patch.object(
                story_bot, "fetch_openverse_photo", return_value=(None, None)
            ), patch.object(
                story_bot, "photo_shows", return_value="neutral"
            ):
                result = story_bot.find_photo(
                    {"image_keywords": ["Saudi oil refinery"]},
                    out_path,
                    context=context,
                    bank=bank,
                )
            return result, bank

    def test_story_rejects_neutral_commons_photo_with_unmentioned_year(self):
        result, bank = self._find_neutral_commons(
            "File:A view of the Bahrein Refinery, 1949.jpg",
            "أسعار النفط تتجاوز 96 دولاراً مع توتر في هرمز",
        )

        self.assertIsNone(result)
        self.assertEqual([], bank)

    def test_story_keeps_neutral_historical_photo_when_year_matches_frame(self):
        result, bank = self._find_neutral_commons(
            "File:Saudi oil refinery, 1949.jpg",
            "كيف بدأ إنتاج النفط في السعودية عام 1949؟",
        )

        self.assertIsNone(result)
        self.assertEqual(1, len(bank))


if __name__ == "__main__":
    unittest.main()
