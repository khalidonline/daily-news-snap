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
    def make_module(self, verdicts, calls, *, local_marker=False, pexels_key="key"):
        def write(path, label, marker=False):
            Path(path).write_bytes(label.encode("utf-8"))
            if marker:
                Path(str(path) + ".exempt").write_text(
                    f"local:{label}.jpg", encoding="utf-8")
            return str(path)

        def local(queries_ar, queries_en, out_path,
                  respect_cooldown=True, exclude=()):
            calls.append("local")
            return write(out_path, "local", local_marker), "Local credit"

        def article(url, out_path):
            calls.append("article")
            return write(out_path, "article"), "aawsat.com"

        def spa(queries_ar, out_path):
            calls.append("spa")
            return write(out_path, "spa"), "واس"

        def commons(queries, out_path, need_saudi=None, min_hits=None,
                    subject_mode=False):
            calls.append("commons")
            return write(out_path, "commons"), "Commons credit"

        def loc(queries, out_path, need_saudi=None, min_hits=None,
                subject_mode=False):
            calls.append("loc")
            return write(out_path, "loc"), "Library of Congress"

        def openverse(queries, out_path, need_saudi=None, min_hits=None,
                      subject_mode=False):
            calls.append("openverse")
            return write(out_path, "openverse"), "Openverse credit"

        def stock(queries, out_path, need_saudi=None):
            calls.append("stock")
            return write(out_path, "stock")

        def judge(path, context):
            label = Path(path).read_bytes().decode("utf-8")
            return verdicts[label]

        return SimpleNamespace(
            IMAGE_SOURCE="auto",
            PEXELS_API_KEY=pexels_key,
            DOMAIN_CREDITS={"aawsat.com": "الشرق الأوسط"},
            photo_shows=judge,
            fetch_local_photo=local,
            fetch_article_photo=article,
            fetch_spa_photo=spa,
            fetch_commons_photo=commons,
            fetch_loc_photo=loc,
            fetch_openverse_photo=openverse,
            fetch_photo=stock,
        )

    def remember_story(self, *, scope="saudi"):
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "Apple تغيّر شيئاً مهماً في iPhone",
                "summary": "التغيير يصل للمستخدمين في السعودية.",
                "takeaway": "قد يؤثر على قرار الشراء القادم.",
                "link": "https://aawsat.com/story",
                "scope": scope,
                "image_queries": ["apple iphone saudi arabia"],
                "image_queries_ar": ["آيفون"],
            }]
        })

    def run_auto(self, fake, hero):
        daily_news_runner.install_auto_image_selector(fake)
        return fake.fetch_local_photo(
            ["آيفون"], ["apple iphone saudi arabia"], hero)

    def test_later_yes_beats_earlier_neutral_in_one_auto_search(self):
        calls = []
        fake = self.make_module({
            "local": "neutral", "article": "yes", "spa": "no",
            "commons": "no", "loc": "no", "openverse": "no", "stock": "no",
        }, calls)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "الشرق الأوسط")
            self.assertEqual(hero.read_bytes(), b"article")

        self.assertEqual(calls, ["local", "article"])

    def test_article_neutral_is_the_only_last_resort_when_no_direct_photo_exists(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "neutral", "spa": "neutral",
            "commons": "neutral", "loc": "no", "openverse": "neutral",
            "stock": "no",
        }, calls)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "الشرق الأوسط")
            self.assertEqual(hero.read_bytes(), b"article")

        self.assertEqual(
            calls, ["local", "article", "spa", "commons", "loc", "openverse", "stock"])

    def test_no_candidate_is_never_promoted(self):
        calls = []
        fake = self.make_module({
            name: "no" for name in
            ("local", "article", "spa", "commons", "loc", "openverse", "stock")
        }, calls)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)

    def test_neutral_fallback_does_not_keep_provider_credit(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)


    def test_local_neutral_is_not_promoted_or_left_exempt(self):
        calls = []
        fake = self.make_module({
            "local": "neutral", "article": "no", "spa": "no",
            "commons": "no", "loc": "no", "openverse": "no", "stock": "no",
        }, calls, local_marker=True)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "الشرق الأوسط")
            self.assertEqual(hero.read_bytes(), b"article")
            self.assertFalse(Path(str(hero) + ".exempt").exists())


    def test_article_neutral_fallback_does_not_inherit_rejected_local_marker(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "neutral", "spa": "no",
            "commons": "no", "loc": "no", "openverse": "no", "stock": "no",
        }, calls, local_marker=True)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)
            self.assertFalse(Path(str(hero) + ".exempt").exists())


    def test_world_story_skips_spa_and_rejects_neutral_commons(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "yes",
            "commons": "neutral", "loc": "no", "openverse": "no", "stock": "no",
        }, calls)
        self.remember_story(scope="world")

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)
        self.assertNotIn("spa", calls)


    def test_downstream_legacy_provider_is_suppressed_after_auto_exhaustion(self):
        calls = []
        fake = self.make_module({
            name: "no" for name in
            ("local", "article", "spa", "commons", "loc", "openverse", "stock")
        }, calls)
        self.remember_story()
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, _ = fake.fetch_local_photo(
                ["آيفون"], ["apple iphone saudi arabia"], hero)
            self.assertIsNone(photo)
            before = list(calls)
            photo, credit = fake.fetch_article_photo("https://aawsat.com/story", hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)
            self.assertEqual(calls, before)


if __name__ == "__main__":
    unittest.main()
