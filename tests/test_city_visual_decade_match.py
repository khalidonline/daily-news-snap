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


if __name__ == "__main__":
    unittest.main()
