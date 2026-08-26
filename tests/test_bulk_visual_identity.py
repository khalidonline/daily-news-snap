import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tools.bulk_visual_identity import (
    choose_unique_logo_slug,
    corroborated_org_qids,
    discover_wikidata_logo_for_terms,
    download_commons_logo,
    discover_verified_logo_identity,
)


class BulkVisualIdentityTests(unittest.TestCase):
    def test_unique_exact_alias_match_is_accepted(self):
        index = {"apple.com": ["Apple", "Steve Jobs", "apple.com"]}
        self.assertEqual(choose_unique_logo_slug({"Steve Jobs"}, index), "apple.com")

    def test_ambiguous_alias_match_fails_closed(self):
        index = {
            "tesla.com": ["Elon Musk"],
            "spacex.com": ["Elon Musk"],
        }
        self.assertIsNone(choose_unique_logo_slug({"Elon Musk"}, index))

    def test_substring_does_not_create_logo_identity(self):
        index = {"snap.com": ["Snap"]}
        self.assertIsNone(choose_unique_logo_slug({"Snapdragon"}, index))

    def test_person_only_match_requires_explicit_index_alias(self):
        index = {"apple.com": ["Apple", "Steve Jobs", "apple.com"]}
        self.assertEqual(choose_unique_logo_slug({"Steve Jobs"}, index), "apple.com")
        index = {"apple.com": ["Apple", "apple.com"]}
        self.assertIsNone(choose_unique_logo_slug({"Steve Jobs"}, index))

    @staticmethod
    def _apple_json_get(url):
        if "wbsearchentities" in url:
            return {"search": [{"id": "Q312", "label": "Apple Inc.", "aliases": ["Apple"]}]}
        return {"entities": {"Q312": {
            "labels": {"en": {"value": "Apple Inc."}},
            "aliases": {"en": [{"value": "Apple"}]},
            "claims": {
                "P154": [{"mainsnak": {"datavalue": {"value": "Apple logo black.svg"}}}],
                "P856": [{"mainsnak": {"datavalue": {"value": "https://www.apple.com/"}}}],
            },
        }}}

    def test_wikidata_logo_requires_exact_entity_alias(self):
        logo = discover_wikidata_logo_for_terms({"Apple"}, self._apple_json_get)
        self.assertEqual(logo.domain, "apple.com")
        self.assertEqual(logo.commons_filename, "Apple logo black.svg")
        self.assertIn("Q312", logo.source_url)

    def test_wikidata_logo_rejects_wrong_sense(self):
        def fake(url):
            if "wbsearchentities" in url:
                return {"search": [{"id": "Q3783", "label": "Amazon River", "aliases": ["Amazon"]}]}
            return {"entities": {}}
        self.assertIsNone(discover_wikidata_logo_for_terms({"Amazon.com"}, fake))

    def test_wikidata_logo_requires_both_logo_and_official_site(self):
        def fake(url):
            if "wbsearchentities" in url:
                return {"search": [{"id": "Q1", "label": "Example Corp", "aliases": ["Example Corp"]}]}
            return {"entities": {"Q1": {"claims": {"P154": []}}}}
        self.assertIsNone(discover_wikidata_logo_for_terms({"Example Corp"}, fake))

    def test_ambiguous_exact_wikidata_results_fail_closed(self):
        def fake(url):
            if "wbsearchentities" in url:
                return {"search": [
                    {"id": "Q1", "label": "Example", "aliases": []},
                    {"id": "Q2", "label": "Example Ltd", "aliases": ["Example"]},
                ]}
            return {"entities": {}}
        self.assertIsNone(discover_wikidata_logo_for_terms({"Example"}, fake))

    def test_person_org_relation_must_be_uniquely_corroborated(self):
        entities = {
            "PERSON": {"P108": ["APPLE", "PIXAR"]},
            "APPLE": {"label": "Apple", "aliases": ["Apple Inc."]},
            "PIXAR": {"label": "Pixar", "aliases": []},
        }
        got = corroborated_org_qids(
            "PERSON", {"Apple Inc."}, {"Macintosh"}, entities.__getitem__,
            lambda prop, qid: [],
        )
        self.assertEqual(got, ["APPLE"])

    def test_commons_download_uses_raster_thumb_and_guard(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.png"
            Image.new("RGB", (80, 80), "white").save(source)
            # Add visible non-flat content so the render guard accepts it.
            image = Image.open(source)
            for x in range(20, 60):
                for y in range(20, 60):
                    image.putpixel((x, y), (0, 0, 0))
            image.save(source)
            requested = []

            def json_get(url):
                return {"query": {"pages": {"1": {"imageinfo": [{
                    "url": "https://example.invalid/original.svg",
                    "thumburl": source.as_uri(),
                }]}}}}

            def bytes_get(url):
                requested.append(url)
                return Path(url.removeprefix("file://")).read_bytes()

            target = Path(td) / "logo.png"
            self.assertEqual(download_commons_logo("Mark.svg", "Mark", target, json_get, bytes_get), target)
            self.assertEqual(requested, [source.as_uri()])
            with Image.open(target) as saved:
                self.assertEqual(saved.format, "PNG")

    @patch("tools.bulk_visual_identity.discover_wikidata_logo_for_terms")
    @patch("tools.bulk_visual_identity.story_identity_terms")
    @patch("tools.bulk_visual_identity.sb.story_aliases")
    def test_direct_discovery_excludes_incidental_approved_photo_tags(
            self, aliases, identity_terms, discover):
        story = "Canonical company story"
        aliases.return_value = {"Canonical Corp"}
        identity_terms.return_value = {"Canonical Corp", "Incidental Sponsor"}
        discover.return_value = None

        with patch.dict("tools.bulk_visual_identity.sb._STORY_PERSONS", {story: []}, clear=False):
            self.assertIsNone(discover_verified_logo_identity(story))

        discover.assert_called_once()
        self.assertEqual(discover.call_args.args[0], {"Canonical Corp"})
        identity_terms.assert_not_called()


if __name__ == "__main__":
    unittest.main()
