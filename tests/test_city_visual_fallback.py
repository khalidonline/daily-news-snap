import tempfile
import unittest
from pathlib import Path

import city_visual_v3 as cvf


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
                cvf.reviewed_city_exact_match(
                    Path(td) / "old-riyadh-souq.jpg",
                    frame,
                    index,
                    aliases=["Riyadh", "الرياض"],
                )
            )
            self.assertFalse(
                cvf.reviewed_city_exact_match(
                    Path(td) / "riyadh-1977-construction.jpg",
                    frame,
                    index,
                    aliases=["Riyadh", "الرياض"],
                )
            )

    def test_exact_city_rung_strips_generic_city_fallback_aliases(self):
        frame = {
            "subject_kind": "place_city",
            "image_keywords": [
                "Riyadh Dammam railway",
                "Riyadh railway station 1951",
                "سكة حديد الرياض الدمام",
                "Riyadh",
                "الرياض",
            ],
            "image_keywords_ar": ["سكة حديد الرياض الدمام"],
        }
        exact = cvf.exact_city_keywords(frame, ["Riyadh", "الرياض"])
        self.assertNotIn("Riyadh", exact)
        self.assertNotIn("الرياض", exact)
        self.assertIn("Riyadh Dammam railway", exact)
        self.assertIn("سكة حديد الرياض الدمام", exact)

    def test_city_fallback_queries_are_generic_city_scenes_only(self):
        queries = cvf.city_fallback_queries(["Riyadh", "الرياض"])
        joined = " ".join(queries).casefold()
        self.assertIn("riyadh skyline", joined)
        self.assertIn("riyadh street", joined)
        self.assertIn("riyadh airport", joined)
        self.assertIn("مطار الرياض", queries)
        self.assertNotIn("الرياض", queries)
        self.assertNotIn("railway", joined)
        self.assertNotIn("1951", joined)
        self.assertNotIn("1977", joined)
        self.assertLessEqual(len(queries), 6)

    def test_city_fallback_rejects_metadata_that_names_another_city(self):
        aliases = ["Riyadh", "الرياض"]
        self.assertFalse(
            cvf.city_candidate_metadata_ok(
                "29 ممشى رياضياً بجدة تزيد أعداد الممارسين", aliases
            )
        )
        self.assertFalse(
            cvf.city_candidate_metadata_ok(
                "Jeddah waterfront public walking path", aliases
            )
        )
        self.assertTrue(
            cvf.city_candidate_metadata_ok(
                "Riyadh skyline and King Fahd Road", aliases
            )
        )

    def test_city_fallback_context_only_requires_the_declared_city(self):
        context = cvf.city_fallback_visual_context(
            "قصة الرياض: من بلدة مسورة إلى عاصمة اقتصادية",
            aliases=["Riyadh", "الرياض"],
        )
        self.assertIn("Riyadh", context)
        self.assertIn("الرياض", context)
        self.assertIn("لا يلزم", context)
        self.assertNotIn("1951", context)
        self.assertNotIn("1977", context)

    def test_riyadh_prompt_prefers_transformation_close_over_weekly_share(self):
        prompt = " ".join(cvf.CITY_PROMPT.split())
        self.assertIn("هذا هو حجم التحول الذي عاشته الرياض", prompt)
        self.assertIn("لا تستخدم حصة أسبوعية", prompt)
        self.assertIn("رقم سنوي", prompt)

    # Regressions from Story to Snapchat #93.
    def test_city_deck_forces_every_frame_out_of_company_logo_mode(self):
        brief = {
            "story": "قصة الرياض: من بلدة مسورة إلى عاصمة اقتصادية",
            "frames": [
                {"subject_kind": "place_city", "heading": "الرياض القديمة"},
                {"subject_kind": "product", "heading": "قطار داخل المدينة"},
                {"subject_kind": "company", "heading": "هيئة تخطط للمدينة"},
            ],
        }
        normalized = cvf.normalize_city_deck_for_visuals(brief)
        self.assertEqual(
            ["place_city", "place_city", "place_city"],
            [frame["subject_kind"] for frame in normalized["frames"]],
        )

    def test_reviewed_exact_rows_find_railway_even_when_year_wording_differs(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "images.txt"
            index.write_text(
                "riyadh-dammam-train.jpg | سكة حديد, قطار الرياض الدمام, Riyadh Dammam railway | archive\n"
                "railway-construction-1951.jpg | سكة حديد الرياض الدمام, 1951, بناء, Riyadh Dammam railway | archive\n"
                "riyadh-skyline.jpg | Riyadh skyline, الرياض | archive\n",
                encoding="utf-8",
            )
            frame = {
                "subject_kind": "place_city",
                "image_keywords": ["Riyadh Dammam railway 1947"],
                "image_keywords_ar": ["سكة حديد الرياض الدمام"],
            }
            rows = cvf.reviewed_city_exact_rows(
                frame, index, aliases=["Riyadh", "الرياض"]
            )
        names = [row["filename"] for row in rows]
        self.assertIn("riyadh-dammam-train.jpg", names)
        self.assertIn("railway-construction-1951.jpg", names)
        self.assertNotIn("riyadh-skyline.jpg", names)

    def test_generic_reviewed_city_rows_require_a_scene_clue_not_bare_city(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "images.txt"
            index.write_text(
                "mcdonalds-riyadh-first.jpg | ماكدونالدز, أول فرع, الرياض | archive\n"
                "riyadh-skyline.jpg | Riyadh skyline, الرياض | archive\n"
                "riyadh-departures.jpg | مطار الرياض, المغادرون | archive\n",
                encoding="utf-8",
            )
            rows = cvf.reviewed_city_fallback_rows(
                index, aliases=["Riyadh", "الرياض"]
            )
        names = [row["filename"] for row in rows]
        self.assertIn("riyadh-skyline.jpg", names)
        self.assertIn("riyadh-departures.jpg", names)
        self.assertNotIn("mcdonalds-riyadh-first.jpg", names)

    def test_city_fallback_context_has_a_marker_for_scene_only_vision(self):
        context = cvf.city_fallback_visual_context(
            "قصة الرياض: من بلدة مسورة إلى عاصمة اقتصادية",
            aliases=["Riyadh", "الرياض"],
        )
        self.assertTrue(cvf.is_city_fallback_context(context))
        self.assertTrue(context.startswith(cvf.CITY_FALLBACK_MARKER))

    # Regressions from the second live artifact of #93.
    def test_explicit_year_conflict_is_hard_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "images.txt"
            index.write_text(
                "railway-construction-1951.jpg | الرياض, 1951, بناء, Riyadh Dammam railway | archive\n"
                "riyadh-1975-construction.jpg | الرياض, 1975, البناء, السبعينات | archive\n"
                "riyadh-1977-construction.jpg | الرياض, 1977, عمران, السبعينات | archive\n",
                encoding="utf-8",
            )
            frame = {
                "subject_kind": "place_city",
                "image_keywords": ["Riyadh construction 1975", "Riyadh 1977"],
                "image_keywords_ar": ["الرياض البناء", "الرياض 1977"],
            }
            rows = cvf.reviewed_city_exact_rows(
                frame, index, aliases=["Riyadh", "الرياض"]
            )
        names = [row["filename"] for row in rows]
        self.assertNotIn("railway-construction-1951.jpg", names)
        self.assertEqual("riyadh-1975-construction.jpg", names[0])
        self.assertIn("riyadh-1977-construction.jpg", names)

    def test_old_riyadh_phrase_is_an_exact_historical_anchor(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "images.txt"
            index.write_text(
                "old-riyadh-souq.jpg | الرياض القديمة, old Riyadh, سوق تقليدي, الرياض | archive\n"
                "riyadh-departures.jpg | مطار الرياض, المغادرون | archive\n",
                encoding="utf-8",
            )
            frame = {
                "subject_kind": "place_city",
                "image_keywords": ["old Riyadh", "Masmak Fort Riyadh"],
                "image_keywords_ar": ["الرياض القديمة", "قصر المصمك"],
            }
            rows = cvf.reviewed_city_exact_rows(
                frame, index, aliases=["Riyadh", "الرياض"]
            )
        self.assertEqual("old-riyadh-souq.jpg", rows[0]["filename"])

    def test_whole_deck_gets_four_exact_assignments_before_any_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "images.txt"
            index.write_text(
                "old-riyadh-souq.jpg | الرياض القديمة, old Riyadh, سوق تقليدي, الرياض | archive\n"
                "railway-construction-1951.jpg | سكة حديد الرياض الدمام, 1951, بناء, Riyadh Dammam railway | archive\n"
                "riyadh-1975-construction.jpg | الرياض, 1975, البناء, السبعينات | archive\n"
                "riyadh-1977-construction.jpg | الرياض, 1977, عمران, السبعينات | archive\n"
                "riyadh-skyline.jpg | Riyadh skyline, الرياض | archive\n",
                encoding="utf-8",
            )
            frames = [
                {"subject_kind": "place_city", "image_keywords": ["old Riyadh"], "image_keywords_ar": ["الرياض القديمة"]},
                {"subject_kind": "place_city", "image_keywords": ["Murabba Palace Riyadh"], "image_keywords_ar": ["قصر المربع"]},
                {"subject_kind": "place_city", "image_keywords": ["Riyadh Dammam railway 1951"], "image_keywords_ar": ["سكة حديد الرياض الدمام"]},
                {"subject_kind": "place_city", "image_keywords": ["Riyadh construction 1975", "Riyadh 1977"], "image_keywords_ar": ["الرياض البناء"]},
                {"subject_kind": "place_city", "image_keywords": ["Riyadh Metro"], "image_keywords_ar": ["مترو الرياض"]},
                {"subject_kind": "place_city", "image_keywords": ["Riyadh skyline"], "image_keywords_ar": ["أفق الرياض"]},
            ]
            assignments = cvf.plan_reviewed_exact_assignments(
                frames, index, aliases=["Riyadh", "الرياض"]
            )
        self.assertGreaterEqual(len(assignments), 4)
        self.assertEqual("old-riyadh-souq.jpg", assignments[0]["filename"])
        self.assertEqual("railway-construction-1951.jpg", assignments[2]["filename"])
        self.assertIn(assignments[3]["filename"], {"riyadh-1975-construction.jpg", "riyadh-1977-construction.jpg"})
        self.assertEqual("riyadh-skyline.jpg", assignments[5]["filename"])

    def test_riyadh_closing_is_locked_to_approved_annual_pos_copy(self):
        brief = {
            "story": "قصة الرياض: من بلدة مسورة إلى عاصمة اقتصادية",
            "frames": [{"heading": f"frame {i}"} for i in range(6)],
        }
        out = cvf.apply_riyadh_closing(brief)
        last = out["frames"][-1]
        self.assertIn("225 مليار ريال", last["text"])
        self.assertIn("مبيعات نقاط البيع", last["text"])
        self.assertEqual("هذا هو حجم التحول الذي عاشته الرياض.", last["punch"])
        self.assertNotIn("34%", last["text"])
        self.assertIn("Riyadh skyline", last["image_keywords"])


if __name__ == "__main__":
    unittest.main()
