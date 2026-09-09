import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import news_bot
from news_visual_recovery import exact_logo_for_targets, normalize_visual_targets


class NewsVisualRecoveryTests(unittest.TestCase):
    def test_scheduled_news_visual_search_is_locked_to_top_story(self):
        stories = [{"headline": "top"}, {"headline": "easy backup"}]
        with patch.object(news_bot, "NEWS_LOCK_TOP_STORY_VISUAL", True, create=True):
            self.assertEqual(news_bot.visual_story_candidates(stories), stories[:1])

    def test_legacy_visual_search_keeps_ranked_backups(self):
        stories = [{"headline": "top"}, {"headline": "backup"}]
        with patch.object(news_bot, "NEWS_LOCK_TOP_STORY_VISUAL", False, create=True):
            self.assertEqual(news_bot.visual_story_candidates(stories), stories)

    def test_visual_failure_names_selected_story_and_infrastructure(self):
        message = news_bot.visual_recovery_failure_message({
            "headline": "OpenAI تحل معضلة رياضية"
        })
        self.assertIn("visual recovery infrastructure failed", message)
        self.assertIn("OpenAI تحل معضلة رياضية", message)

    def test_normalizes_typed_targets_and_drops_invalid_or_duplicate_items(self):
        story = {"visual_targets": [
            {"kind": "organization", "name_en": "OpenAI", "name_ar": "أوبن أي آي"},
            {"kind": "organization", "name_en": " openai ", "name_ar": ""},
            {"kind": "guess", "name_en": "wrong"},
            {"kind": "person", "name_en": "", "name_ar": ""},
            {"kind": "place", "name_en": "Riyadh", "name_ar": "الرياض"},
        ]}

        self.assertEqual(normalize_visual_targets(story), [
            {"kind": "organization", "name_en": "OpenAI", "name_ar": "أوبن أي آي"},
            {"kind": "place", "name_en": "Riyadh", "name_ar": "الرياض"},
        ])

    def test_legacy_queries_become_capped_context_targets(self):
        story = {
            "image_queries": [f"query {i}" for i in range(10)],
            "image_queries_ar": ["سياق عربي"],
        }

        targets = normalize_visual_targets(story)

        self.assertEqual(len(targets), 8)
        self.assertTrue(all(target["kind"] == "context" for target in targets))
        self.assertEqual(targets[0]["name_en"], "query 0")

    def test_exact_openai_logo_resolves(self):
        root = Path(__file__).resolve().parents[1]
        logo, entity = exact_logo_for_targets(
            [{"kind": "organization", "name_en": "OpenAI", "name_ar": ""}],
            root / "images" / "logos",
            root / "images" / "logos" / "index.json",
        )

        self.assertEqual(logo.name, "openai.com-current.png")
        self.assertEqual(entity, "OpenAI")

    def test_secondary_alias_cannot_resolve_wrong_logo(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("Google", "Uber"):
            with self.subTest(name=name):
                logo, entity = exact_logo_for_targets(
                    [{"kind": "organization", "name_en": name, "name_ar": ""}],
                    root / "images" / "logos",
                    root / "images" / "logos" / "index.json",
                )
                self.assertIsNone(logo)
                self.assertIsNone(entity)

    def test_missing_registered_logo_is_fetched_with_verified_domain(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            index = root / "index.json"
            index.write_text(json.dumps({"anthropic.com": ["Anthropic"]}))
            target = [{"kind": "organization", "name_en": "Anthropic"}]
            def fetch(slug, names, require_domain=None):
                self.assertEqual(require_domain, "anthropic.com")
                path = root / (slug + "-current.png")
                path.write_bytes(b"verified-logo")
                return path
            with patch("logo_fetch.fetch_current", side_effect=fetch) as call:
                logo, entity = exact_logo_for_targets(target, root, index)
            self.assertEqual(entity, "Anthropic")
            self.assertTrue(logo.is_file())
            call.assert_called_once()

    def test_acronym_logo_uses_domain_verified_wikidata_fallback(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            index = root / "index.json"
            index.write_text(json.dumps({"oecd.org": ["OECD"]}))
            target = [{"kind": "organization", "name_en": "OECD"}]
            def download(url, path):
                Path(path).write_bytes(b"logo")
            with patch("logo_fetch.fetch_current", return_value=None), \
                 patch("logo_fetch.wikidata_p154_logo", return_value="OECD logo.svg") as identity, \
                 patch("logo_fetch._commons_fileinfo", return_value=[({}, {"thumburl": "https://upload.wikimedia.org/logo.png"})]), \
                 patch("logo_fetch._download", side_effect=download), \
                 patch("logo_fetch._renders_as_a_mark", return_value=True):
                logo, entity = exact_logo_for_targets(target, root, index)
            identity.assert_called_once_with(["OECD"], "oecd.org")
            self.assertTrue(logo.is_file())
            self.assertEqual(entity, "OECD")

    def test_unknown_organization_has_no_logo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "index.json").write_text("{}", encoding="utf-8")
            logo, entity = exact_logo_for_targets(
                [{"kind": "organization", "name_en": "Unknown", "name_ar": ""}],
                root,
                root / "index.json",
            )
        self.assertIsNone(logo)
        self.assertIsNone(entity)


if __name__ == "__main__":
    unittest.main()
