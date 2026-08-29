import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import daily_news_runner


class AutoImageSourcePolicyTests(unittest.TestCase):
    def test_normalize_image_source_defaults_and_aliases(self):
        self.assertEqual(daily_news_runner.normalize_image_source(None), "auto")
        self.assertEqual(daily_news_runner.normalize_image_source(""), "auto")
        self.assertEqual(daily_news_runner.normalize_image_source("spa"), "spa")
        self.assertEqual(daily_news_runner.normalize_image_source("pexels"), "stock")
        self.assertEqual(daily_news_runner.normalize_image_source("bogus"), "auto")

    def make_module(self):
        def noop_pair(*args, **kwargs):
            return None, None

        def noop_photo(*args, **kwargs):
            return None

        return SimpleNamespace(
            LOOKBACK_HOURS=30,
            SYSTEM_PROMPT="old",
            MAX_HEADLINES_TO_MODEL=60,
            summarize=lambda items, already_posted=(), pinned="": {"stories": []},
            _http_get=lambda _: b"<rss><channel></channel></rss>",
            _clean=lambda x: x or "",
            _parse_date=lambda x: None,
            IMAGE_SOURCE="spa",
            PEXELS_API_KEY="key",
            DOMAIN_CREDITS={"aawsat.com": "الشرق الأوسط"},
            photo_shows=lambda path, context: "yes",
            fetch_local_photo=noop_pair,
            fetch_article_photo=noop_pair,
            fetch_spa_photo=noop_pair,
            fetch_commons_photo=noop_pair,
            fetch_loc_photo=noop_pair,
            fetch_openverse_photo=noop_pair,
            fetch_photo=noop_photo,
        )

    def test_configure_defaults_to_auto_and_installs_wrappers(self):
        fake = self.make_module()
        original_local = fake.fetch_local_photo
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IMAGE_SOURCE", None)
            os.environ.pop("LOOKBACK_HOURS", None)
            daily_news_runner.configure(fake)
        self.assertEqual(fake.IMAGE_SOURCE, "auto")
        self.assertIsNot(fake.fetch_local_photo, original_local)

    def test_manual_override_preserves_legacy_provider_functions(self):
        fake = self.make_module()
        original_local = fake.fetch_local_photo
        with patch.dict(os.environ, {"IMAGE_SOURCE": "commons"}, clear=False):
            daily_news_runner.configure(fake)
        self.assertEqual(fake.IMAGE_SOURCE, "commons")
        self.assertIs(fake.fetch_local_photo, original_local)


class RelevanceFirstWrapperTests(unittest.TestCase):
    def make_module(self, verdicts, seen_contexts):
        def write_pair(label, credit):
            def provider(*args, **kwargs):
                out_path = args[-1]
                Path(out_path).write_bytes(label.encode("utf-8"))
                return str(out_path), credit
            return provider

        def write_photo(label):
            def provider(*args, **kwargs):
                out_path = args[1]
                Path(out_path).write_bytes(label.encode("utf-8"))
                return str(out_path)
            return provider

        def judge(path, context):
            label = Path(path).read_bytes().decode("utf-8")
            seen_contexts.append(context)
            return verdicts[label]

        return SimpleNamespace(
            IMAGE_SOURCE="auto",
            PEXELS_API_KEY="key",
            DOMAIN_CREDITS={"aawsat.com": "الشرق الأوسط"},
            photo_shows=judge,
            fetch_local_photo=write_pair("local", "Local credit"),
            fetch_article_photo=write_pair("article", "aawsat.com"),
            fetch_spa_photo=write_pair("spa", "واس"),
            fetch_commons_photo=write_pair("commons", "Commons credit"),
            fetch_loc_photo=write_pair("loc", "Library of Congress"),
            fetch_openverse_photo=write_pair("openverse", "Openverse credit"),
            fetch_photo=write_photo("stock"),
        )

    def remember_story(self):
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "Apple تغيّر شيئاً مهماً في iPhone",
                "summary": "التغيير يصل للمستخدمين في السعودية.",
                "takeaway": "قد يؤثر على قرار الشراء القادم.",
                "image_queries": ["apple iphone saudi arabia"],
                "image_queries_ar": ["آيفون"],
            }]
        })

    def test_neutral_early_source_does_not_beat_later_yes(self):
        seen = []
        fake = self.make_module({
            "local": "neutral", "article": "yes", "spa": "no",
            "commons": "no", "loc": "no", "openverse": "no", "stock": "no",
        }, seen)
        self.remember_story()
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["آيفون"], ["apple iphone saudi arabia"], hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)

            photo, domain = fake.fetch_article_photo("https://aawsat.com/x", hero)
            self.assertEqual(photo, str(hero))
            self.assertEqual(domain, "aawsat.com")
            self.assertEqual(hero.read_bytes(), b"article")

        self.assertTrue(any("Apple تغيّر" in context for context in seen))
        self.assertTrue(any("قرار الشراء" in context for context in seen))

    def test_no_candidate_is_rejected_and_yes_candidate_keeps_metadata(self):
        seen = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "yes",
            "commons": "no", "loc": "no", "openverse": "no", "stock": "no",
        }, seen)
        self.remember_story()
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, _ = fake.fetch_local_photo(
                ["آيفون"], ["apple iphone saudi arabia"], hero)
            self.assertIsNone(photo)
            photo, _ = fake.fetch_article_photo("https://aawsat.com/x", hero)
            self.assertIsNone(photo)
            photo, credit = fake.fetch_spa_photo(["آيفون"], hero)
            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "واس")
            self.assertEqual(hero.read_bytes(), b"spa")

    def test_neutral_stock_is_not_accepted_when_no_direct_match_exists(self):
        seen = []
        fake = self.make_module({
            "local": "neutral", "article": "neutral", "spa": "neutral",
            "commons": "neutral", "loc": "neutral", "openverse": "neutral",
            "stock": "neutral",
        }, seen)
        self.remember_story()
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            self.assertIsNone(fake.fetch_local_photo(
                ["آيفون"], ["apple iphone saudi arabia"], hero)[0])
            self.assertIsNone(fake.fetch_article_photo("https://aawsat.com/x", hero)[0])
            self.assertIsNone(fake.fetch_spa_photo(["آيفون"], hero)[0])
            self.assertIsNone(fake.fetch_commons_photo(
                ["apple iphone saudi arabia"], hero, need_saudi=True)[0])
            self.assertIsNone(fake.fetch_loc_photo(
                ["apple iphone saudi arabia"], hero, need_saudi=True)[0])
            self.assertIsNone(fake.fetch_openverse_photo(
                ["apple iphone saudi arabia"], hero, need_saudi=True)[0])
            self.assertIsNone(fake.fetch_photo(
                ["apple iphone saudi arabia"], hero, need_saudi=True))


if __name__ == "__main__":
    unittest.main()
