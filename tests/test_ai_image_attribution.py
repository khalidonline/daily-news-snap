# Regression coverage for AI-generated image attribution across publish flows.
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops

import news_bot
import story_bot
import topic_snapchat


class AIImageAttributionTests(unittest.TestCase):
    def _write_photo(self, path):
        Image.new("RGB", (1080, 720), (210, 210, 210)).save(path, "JPEG")
        return path

    def _news_brief(self):
        return {
            "title": "عنوان تجريبي",
            "body": "نص قصير لاختبار بطاقة الخبر.",
            "takeaway": "الخلاصة تظهر هنا.",
            "sources": ["Reuters"],
        }

    def test_news_generated_photo_matches_same_card_without_photo_credit(self):
        """The .generated marker must suppress photo attribution on the card."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            photo = self._write_photo(td / "hero.jpg")
            marker = Path(str(photo) + ".generated")
            marker.write_text("1", encoding="utf-8")

            generated_out = td / "generated.png"
            news_bot.render_story(
                self._news_brief(), generated_out,
                photo_path=photo, photo_credit="صورة مولّدة بالذكاء الاصطناعي",
            )

            marker.unlink()
            creditless_out = td / "creditless.png"
            news_bot.render_story(
                self._news_brief(), creditless_out,
                photo_path=photo, photo_credit=None,
            )

            with Image.open(generated_out) as generated, Image.open(creditless_out) as creditless:
                diff = ImageChops.difference(generated.convert("RGB"), creditless.convert("RGB"))
                self.assertIsNone(
                    diff.getbbox(),
                    "generated news photo should render exactly like a creditless photo",
                )

    def test_topic_generated_photo_passes_no_credit_to_renderer(self):
        seen = {}

        def renderer(brief, out_path, photo_path=None, photo_credit=None):
            seen["credit"] = photo_credit
            return out_path

        wrapped = topic_snapchat._creditless_renderer(
            renderer, "صورة مولّدة بالذكاء الاصطناعي"
        )
        with tempfile.TemporaryDirectory() as td:
            photo = Path(td) / "hero.jpg"
            photo.write_bytes(b"image")
            Path(str(photo) + ".generated").write_text("1", encoding="utf-8")
            wrapped({}, Path(td) / "out.png", photo, "provider credit")

        self.assertIsNone(seen["credit"])

    def test_story_generated_frames_do_not_add_ai_photo_source(self):
        brief = {
            "title": "قصة تجريبية",
            "sources": ["Reuters"],
            "frames": [
                {"heading": f"لقطة {n}", "text": "نص تجريبي", "punch": ""}
                for n in range(1, 5)
            ],
        }
        captured_footers = []

        def fake_render(path, *args, **kwargs):
            captured_footers.append(kwargs.get("footer"))
            return path

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            photos = []
            for n in range(1, 5):
                photo = td / f"photo-{n}.jpg"
                photo.write_bytes(b"image")
                photos.append(str(photo))

            Path(photos[1] + ".generated").write_text("1", encoding="utf-8")
            Path(photos[3] + ".generated").write_text("1", encoding="utf-8")

            with patch.object(story_bot, "OUT_DIR", td), patch.object(
                story_bot, "render_frame", side_effect=fake_render
            ):
                story_bot.build_frames(brief, "test", photos)

        self.assertIsNone(captured_footers[1])
        self.assertEqual(captured_footers[3], "المصدر: Reuters")


if __name__ == "__main__":
    unittest.main()
