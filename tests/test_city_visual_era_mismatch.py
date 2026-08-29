import tempfile
import unittest
from pathlib import Path

import city_visual_v3 as cvf


class CityVisualEraMismatchTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
