import tempfile
import unittest
from pathlib import Path

import city_visual_v3 as cvf


class CityVisualDecadeMatchTests(unittest.TestCase):
    def test_1970s_target_matches_reviewed_1975_or_1977_not_1951(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "images.txt"
            index.write_text(
                "railway-construction-1951.jpg | الرياض, 1951, بناء, Riyadh Dammam railway | archive\n"
                "riyadh-1975-construction.jpg | الرياض, 1975, البناء, السبعينات | أرشيف الرياض التاريخي\n"
                "riyadh-1977-construction.jpg | الرياض, 1977, عمران, السبعينات | أرشيف الرياض التاريخي\n",
                encoding="utf-8",
            )
            frame = {
                "subject_kind": "place_city",
                "image_keywords": ["Riyadh 1970s construction", "Qasr Al Hokm Riyadh"],
                "image_keywords_ar": ["الرياض السبعينات", "بناء الرياض"],
            }
            rows = cvf.reviewed_city_exact_rows(
                frame, index, aliases=["Riyadh", "الرياض"]
            )

        names = [row["filename"] for row in rows]
        self.assertIn("riyadh-1975-construction.jpg", names)
        self.assertIn("riyadh-1977-construction.jpg", names)
        self.assertNotIn("railway-construction-1951.jpg", names)

    def test_specific_city_beats_cannot_be_satisfied_by_generic_city_scene(self):
        aliases = ["Riyadh", "الرياض"]
        specific_frames = [
            {
                "image_keywords": ["Murabba Palace Riyadh"],
                "image_keywords_ar": ["قصر المربع"],
            },
            {
                "image_keywords": ["Riyadh Metro", "Riyadh Metro station"],
                "image_keywords_ar": ["مترو الرياض"],
            },
            {
                "image_keywords": ["Riyadh 1970s construction"],
                "image_keywords_ar": ["الرياض السبعينات"],
            },
        ]
        for frame in specific_frames:
            with self.subTest(frame=frame):
                self.assertFalse(
                    cvf.city_frame_allows_generic_fallback(frame, aliases)
                )

        generic_frame = {
            "image_keywords": ["Riyadh skyline", "Riyadh street"],
            "image_keywords_ar": ["أفق الرياض"],
        }
        self.assertTrue(
            cvf.city_frame_allows_generic_fallback(generic_frame, aliases)
        )

    def test_spa_item_explicitly_naming_another_city_is_rejected(self):
        aliases = ["Riyadh", "الرياض"]
        jeddah = {
            "title": "29 ممشى رياضياً بجدة تزيد أعداد الممارسين",
            "tags": [{"name": "الرياض"}, {"name": "رياضة"}],
        }
        riyadh = {
            "title": "افتتاح محطة مترو الرياض الجديدة",
            "tags": [{"name": "الرياض"}, {"name": "مترو"}],
        }
        self.assertFalse(cvf.city_spa_metadata_ok(jeddah, aliases))
        self.assertTrue(cvf.city_spa_metadata_ok(riyadh, aliases))

    def test_modern_old_riyadh_souq_cannot_match_1902_historical_frame(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "images.txt"
            index.write_text(
                "old-riyadh-souq.jpg | الرياض القديمة, old Riyadh, سوق تقليدي, الرياض | Wikimedia Commons\n"
                "riyadh-1975-construction.jpg | الرياض, 1975, البناء, السبعينات | أرشيف الرياض التاريخي\n",
                encoding="utf-8",
            )
            frame = {
                "subject_kind": "place_city",
                "image_keywords": ["Old Riyadh 1902 city wall"],
                "image_keywords_ar": ["الرياض القديمة", "سور الرياض 1902"],
            }
            rows = cvf.reviewed_city_exact_rows(
                frame, index, aliases=["Riyadh", "الرياض"]
            )

        self.assertNotIn(
            "old-riyadh-souq.jpg",
            [row["filename"] for row in rows],
        )

    def test_targeted_web_requires_declared_city_and_compatible_era(self):
        aliases = ["Riyadh", "الرياض"]
        old_frame = {
            "image_keywords": ["Old Riyadh city wall"],
            "image_keywords_ar": ["الرياض القديمة", "سور الرياض القديم"],
        }
        expansion_frame = {
            "image_keywords": ["Al Malaz Riyadh", "Riyadh 1960s"],
            "image_keywords_ar": ["حي الملز", "الرياض الستينات"],
        }

        self.assertFalse(
            cvf.city_target_metadata_ok(
                "File:Old town of Tharmada, central Saudi Arabia - 2020.jpg",
                old_frame,
                aliases,
            )
        )
        self.assertTrue(
            cvf.city_target_metadata_ok(
                "Workers breaking old city walls of Riyadh 1950 Riyadh",
                old_frame,
                aliases,
            )
        )
        self.assertFalse(
            cvf.city_target_metadata_ok(
                "المسار الرياضي يعزز جودة الحياة في الرياض 2025",
                expansion_frame,
                aliases,
            )
        )
        self.assertTrue(
            cvf.city_target_metadata_ok(
                "Al-Dhahirah Street in Riyadh, 1959 or 1960",
                expansion_frame,
                aliases,
            )
        )

    def test_riyadh_historical_target_queries_use_precise_archive_anchors(self):
        aliases = ["Riyadh", "الرياض"]
        old_frame = {
            "image_keywords": ["Old Riyadh", "Riyadh old town"],
            "image_keywords_ar": ["الرياض القديمة", "سوق الرياض القديم"],
        }
        expansion_frame = {
            "image_keywords": ["Al Malaz Riyadh", "Riyadh 1960s"],
            "image_keywords_ar": ["حي الملز", "الرياض"],
        }

        old_terms = cvf.targeted_city_keywords(old_frame, aliases)
        expansion_terms = cvf.targeted_city_keywords(expansion_frame, aliases)

        self.assertEqual("Workers breaking old city walls of Riyadh", old_terms[0])
        self.assertIn("Al-Dhahirah Street Riyadh 1960s", expansion_terms)
        self.assertNotIn("Riyadh", expansion_terms)
        self.assertNotIn("الرياض", expansion_terms)


if __name__ == "__main__":
    unittest.main()
