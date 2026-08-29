import tempfile
import unittest
from pathlib import Path

import story_focus


class CityVisualFallbackTests(unittest.TestCase):
    def test_reviewed_exact_city_asset_needs_a_non_city_visual_clue(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "images.txt"
            index.write_text(
                "old-riyadh-souq.jpg | الرياض القديمة, old Riyadh, سوق تقليدي | archive\n"
                "riyadh-1977-construction.jpg | الرياض, 1977, عمران | archive\n",
                encoding="utf-8",
            )
            frame = {
                "subject_kind": "place_city",
                "image_keywords": ["old Riyadh", "Riyadh mud wall", "Riyadh old souq"],
                "image_keywords_ar": ["الرياض القديمة", "سور الرياض القديم"],
            }
            self.assertTrue(
                story_focus.reviewed_city_exact_match(
                    Path(td) / "old-riyadh-souq.jpg",
                    frame,
                    index,
                    aliases=["Riyadh", "الرياض"],
                )
            )
            self.assertFalse(
                story_focus.reviewed_city_exact_match(
                    Path(td) / "riyadh-1977-construction.jpg",
                    frame,
                    index,
                    aliases=["Riyadh", "الرياض"],
                )
            )

    def test_exact_city_rung_strips_generic_city_fallback_aliases(self):
        brief = {
            "frames": [{
                "subject_kind": "place_city",
                "image_keywords": ["Riyadh Dammam railway", "Riyadh railway station 1951"],
                "image_keywords_ar": ["سكة حديد الرياض الدمام"],
            }]
        }
        prepared = story_focus.prepare_city_visual_search(
            brief, aliases=["Riyadh", "الرياض"]
        )
        frame = prepared["frames"][0]
        # Keep the old public payload for compatibility, but the selector's
        # exact rung must remove the bare city aliases before it searches.
        self.assertIn("Riyadh", frame["image_keywords"])
        exact = story_focus.exact_city_keywords(frame, ["Riyadh", "الرياض"])
        self.assertNotIn("Riyadh", exact)
        self.assertNotIn("الرياض", exact)
        self.assertIn("Riyadh Dammam railway", exact)
        self.assertIn("سكة حديد الرياض الدمام", exact)

    def test_city_fallback_queries_are_generic_city_scenes_only(self):
        queries = story_focus.city_fallback_queries(["Riyadh", "الرياض"])
        joined = " ".join(queries).casefold()
        self.assertIn("riyadh skyline", joined)
        self.assertIn("riyadh street", joined)
        self.assertIn("riyadh airport", joined)
        self.assertNotIn("railway", joined)
        self.assertNotIn("1951", joined)
        self.assertNotIn("1977", joined)
        self.assertLessEqual(len(queries), 6)

    def test_city_fallback_rejects_metadata_that_names_another_city(self):
        aliases = ["Riyadh", "الرياض"]
        self.assertFalse(
            story_focus.city_candidate_metadata_ok(
                "29 ممشى رياضياً بجدة تزيد أعداد الممارسين", aliases
            )
        )
        self.assertFalse(
            story_focus.city_candidate_metadata_ok(
                "Jeddah waterfront public walking path", aliases
            )
        )
        self.assertTrue(
            story_focus.city_candidate_metadata_ok(
                "Riyadh skyline and King Fahd Road", aliases
            )
        )

    def test_city_fallback_context_only_requires_the_declared_city(self):
        context = story_focus.city_fallback_visual_context(
            "قصة الرياض: من بلدة مسورة إلى عاصمة اقتصادية",
            aliases=["Riyadh", "الرياض"],
        )
        self.assertIn("Riyadh", context)
        self.assertIn("الرياض", context)
        self.assertIn("لا يلزم", context)
        self.assertNotIn("1951", context)
        self.assertNotIn("1977", context)

    def test_riyadh_prompt_prefers_transformation_close_over_weekly_share(self):
        prompt = " ".join(story_focus.FOCUS_PROMPT.split())
        self.assertIn("هذا هو حجم التحول الذي عاشته الرياض", prompt)
        self.assertIn("لا تستخدم حصة أسبوعية", prompt)
        self.assertIn("رقم سنوي", prompt)


if __name__ == "__main__":
    unittest.main()
