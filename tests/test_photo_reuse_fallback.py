import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import daily_news_fresh_runner
import daily_news_runner


class RecentPhotoFallbackTests(unittest.TestCase):
    def make_module(self):
        def recent_only(queries_ar, queries_en, out_path,
                        respect_cooldown=True, exclude=()):
            candidate = Path(out_path)
            candidate.write_bytes(b"recent-sama-photo")
            Path(str(candidate) + ".recentkeep").write_bytes(b"recent-sama-photo")
            candidate.unlink(missing_ok=True)
            return None, None

        def none_pair(*args, **kwargs):
            return None, None

        def none_photo(*args, **kwargs):
            return None

        return SimpleNamespace(
            IMAGE_SOURCE="auto",
            PEXELS_API_KEY="",
            DOMAIN_CREDITS={},
            photo_shows=lambda path, context: "no",
            fetch_local_photo=recent_only,
            fetch_article_photo=none_pair,
            fetch_spa_photo=none_pair,
            fetch_commons_photo=none_pair,
            fetch_loc_photo=none_pair,
            fetch_openverse_photo=none_pair,
            fetch_photo=none_photo,
            recent_fallback=lambda out_path: str(out_path),
        )

    def install(self, fake):
        daily_news_runner.install_auto_image_selector(fake)
        daily_news_fresh_runner.install_recent_photo_fail_closed(fake)

    def remember(self, headline, query):
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": headline,
                "summary": "summary",
                "takeaway": "takeaway",
                "link": "",
                "scope": "saudi",
                "image_queries": [query],
                "image_queries_ar": [query],
            }]
        })

    def test_recent_photo_is_not_exposed_as_legacy_fallback(self):
        fake = self.make_module()
        self.install(fake)
        self.remember("استثمارات المركزي السعودي", "sama")

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(["sama"], ["sama"], hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)
            self.assertFalse(Path(str(hero) + ".recentkeep").exists())
            self.assertIsNone(fake.recent_fallback(hero))

    def test_recent_fallback_cannot_leak_from_one_story_to_the_next(self):
        fake = self.make_module()
        self.install(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            self.remember("استثمارات المركزي السعودي", "sama")
            fake.fetch_local_photo(["sama"], ["sama"], hero)

            # The next ranked story must start clean; a recent SAMA candidate
            # cannot become its eventual fallback after fresh imagery fails.
            self.remember("خبر سعودي مختلف", "different")
            photo, credit = fake.fetch_local_photo(
                ["different"], ["different"], hero
            )
            self.assertIsNone(photo)
            self.assertIsNone(credit)
            self.assertFalse(Path(str(hero) + ".recentkeep").exists())
            self.assertIsNone(fake.recent_fallback(hero))


if __name__ == "__main__":
    unittest.main()
