import unittest

from tools.bulk_visual_sources import (
    StoryBeat,
    discover_commons,
    discover_first_party,
    discover_loc,
    discover_openverse,
    plan_story_beats,
)


class StoryBeatPlannerTests(unittest.TestCase):
    def test_person_story_starts_with_exact_person_identity(self):
        beats = plan_story_beats("Jack Bogle: أنشأ صندوق المؤشرات ورفض أن يصبح ملياردير")
        self.assertEqual(beats[0].key, "person")
        self.assertIn("Jack Bogle", beats[0].required_identity)

    def test_company_story_has_four_distinct_beats(self):
        beats = plan_story_beats("قصة NVIDIA: من رقائق الألعاب إلى أغلى شركة في العالم")
        self.assertEqual([b.key for b in beats[:4]],
                         ["origin", "early_operation", "turning_point", "modern_result"])

    def test_queries_are_identity_anchored(self):
        for beat in plan_story_beats("قصة NVIDIA: من رقائق الألعاب إلى أغلى شركة في العالم"):
            self.assertTrue(beat.required_identity)
            self.assertTrue(all(any(identity in query for identity in beat.required_identity)
                                for query in beat.queries))

    def test_commons_filters_artwork_and_preserves_license(self):
        beat = StoryBeat("person", ("Jack Bogle",), ("Jack Bogle", "John C. Bogle"))
        def fake_json_get(url):
            return {"query": {"pages": {
                "1": {"pageid": 1, "title": "File:John C Bogle 2007.jpg", "imageinfo": [{
                    "url": "https://upload.wikimedia.org/bogle.jpg", "descriptionurl": "https://commons.wikimedia.org/wiki/File:John_C_Bogle_2007.jpg",
                    "width": 594, "height": 792, "extmetadata": {"ImageDescription": {"value": "John C. Bogle in 2007"}, "Artist": {"value": "Bill Cramer"}, "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]},
                "2": {"pageid": 2, "title": "File:Jack Bogle illustration.svg", "imageinfo": [{
                    "url": "https://upload.wikimedia.org/bogle-art.svg", "descriptionurl": "https://commons.wikimedia.org/wiki/File:Jack_Bogle_illustration.svg",
                    "width": 800, "height": 800, "extmetadata": {"ImageDescription": {"value": "Illustration of Jack Bogle"}, "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]},
            }}}
        found = discover_commons(beat, json_get=fake_json_get)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].source_id, "commons:1")
        self.assertEqual(found[0].license, "CC BY-SA 4.0")
        self.assertIn("John C. Bogle", found[0].description)

    def test_structured_adapters_reject_missing_stable_identity_or_page(self):
        beat = StoryBeat("person", ("Jack Bogle",), ("Jack Bogle",))
        commons_base = {"title": "File:Jack Bogle.jpg", "imageinfo": [{
            "url": "https://upload.wikimedia.org/bogle.jpg", "width": 800,
            "height": 800, "extmetadata": {"ImageDescription": {"value": "Jack Bogle"}},
        }]}
        self.assertEqual(discover_commons(beat, json_get=lambda _: {
            "query": {"pages": {"x": commons_base}}}), [])
        with_id = dict(commons_base, pageid=3)
        self.assertEqual(discover_commons(beat, json_get=lambda _: {
            "query": {"pages": {"x": with_id}}}), [])

        self.assertEqual(discover_loc(beat, json_get=lambda _: {"results": [{
            "title": "Jack Bogle", "description": ["Jack Bogle"],
            "image_url": ["https://tile.loc.gov/x.jpg"],
        }]}), [])
        self.assertEqual(discover_openverse(beat, json_get=lambda _: {"results": [{
            "title": "Jack Bogle", "url": "https://img.test/a.jpg",
            "foreign_landing_url": "https://source.test/a",
        }]}), [])

    def test_loc_and_openverse_keep_provenance(self):
        beat = StoryBeat("origin", ("NVIDIA origin",), ("NVIDIA",))
        loc = discover_loc(beat, json_get=lambda url: {"results": [{"id": "https://www.loc.gov/item/1/", "title": "NVIDIA headquarters", "description": ["NVIDIA building"], "image_url": ["https://tile.loc.gov/x.jpg"], "resources": [{"width": 900, "height": 700}]}]})
        self.assertEqual(loc[0].source_id, "loc:1")
        ov = discover_openverse(beat, json_get=lambda url: {"results": [{"id": "abc", "title": "NVIDIA headquarters", "url": "https://img.test/a.jpg", "foreign_landing_url": "https://source.test/a", "creator": "A", "license": "by", "license_url": "https://creativecommons.org/licenses/by/4.0/", "width": 900, "height": 700}]})
        self.assertEqual(ov[0].source_page, "https://source.test/a")
        self.assertEqual(ov[0].license, "by")

    def test_first_party_rejects_unverified_page_and_accepts_referenced_cdn(self):
        beat = StoryBeat("modern_result", ("NVIDIA modern",), ("NVIDIA",))
        self.assertEqual(discover_first_party(beat, "nvidia.com", page_url="https://evil.test/news", html_get=lambda _: '<img src="https://cdn.test/a.jpg">'), [])
        found = discover_first_party(beat, "nvidia.com", page_url="https://www.nvidia.com/news", html_get=lambda _: '<meta property="og:image" content="https://cdn.nvidia.test/a.jpg"><title>NVIDIA News</title>')
        self.assertEqual(found[0].source_page, "https://www.nvidia.com/news")
        self.assertEqual(found[0].license, "")

    def test_first_party_source_id_is_stable_across_page_image_order(self):
        beat = StoryBeat("modern_result", ("NVIDIA modern",), ("NVIDIA",))
        first = discover_first_party(
            beat, "nvidia.com", page_url="https://www.nvidia.com/news",
            html_get=lambda _: '<title>NVIDIA News</title><img src="/a.jpg"><img src="/b.jpg">')
        second = discover_first_party(
            beat, "nvidia.com", page_url="https://www.nvidia.com/news",
            html_get=lambda _: '<title>NVIDIA News</title><img src="/b.jpg"><img src="/a.jpg">')
        ids_by_url = {item.direct_url: item.source_id for item in first}
        self.assertEqual(ids_by_url,
                         {item.direct_url: item.source_id for item in second})


if __name__ == "__main__":
    unittest.main()
