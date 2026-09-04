import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import daily_news_runner


class ArticleImageRelevanceRegressionTests(unittest.TestCase):
    def test_neutral_article_photo_is_rejected_instead_of_used_as_fallback(self):
        calls = []

        def write(path, label):
            Path(path).write_bytes(label.encode("utf-8"))
            return str(path)

        def local(queries_ar, queries_en, out_path,
                  respect_cooldown=True, exclude=()):
            calls.append("local")
            return None, None

        def article(url, out_path):
            calls.append("article")
            return write(out_path, "article"), "arabnews.com"

        def pair_no(*args, **kwargs):
            calls.append("other")
            return None, None

        def stock_no(*args, **kwargs):
            calls.append("stock")
            return None

        fake = SimpleNamespace(
            IMAGE_SOURCE="auto",
            PEXELS_API_KEY="key",
            DOMAIN_CREDITS={"arabnews.com": "Arab News"},
            photo_shows=lambda path, context: "neutral",
            fetch_local_photo=local,
            fetch_article_photo=article,
            fetch_spa_photo=pair_no,
            fetch_commons_photo=pair_no,
            fetch_loc_photo=pair_no,
            fetch_openverse_photo=pair_no,
            fetch_photo=stock_no,
        )

        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "stc تطلق colab لبناء المشاريع الرقمية الناشئة",
                "summary": "أعلنت مجموعة stc إطلاق colab في LEAP 2026.",
                "takeaway": "المنصة تسرع الشركات الناشئة من الفكرة إلى البناء.",
                "link": "https://arabnews.com/stc-colab",
                "scope": "saudi",
                "image_queries": ["stc colab LEAP 2026"],
                "image_queries_ar": ["stc colab ليب 2026"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["stc colab ليب 2026"], ["stc colab LEAP 2026"], hero
            )

        self.assertIsNone(photo)
        self.assertIsNone(credit)
        self.assertIn("article", calls)


if __name__ == "__main__":
    unittest.main()
