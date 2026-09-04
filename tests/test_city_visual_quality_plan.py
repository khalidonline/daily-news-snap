import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw

import city_visual_v3 as cvf
import news_bot


class CityVisualQualityPlanTests(unittest.TestCase):
    def _dusty(self):
        img = Image.new("RGB", (480, 320), (224, 151, 91))
        draw = ImageDraw.Draw(img)
        for x, h in ((35, 65), (90, 100), (155, 72), (220, 125), (300, 88), (380, 110)):
            draw.rectangle((x, 250 - h, x + 32, 250), fill=(126, 99, 78))
        draw.rectangle((0, 250, 480, 320), fill=(171, 121, 82))
        return img

    def _clear(self):
        img = Image.new("RGB", (480, 320), (103, 178, 226))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 205, 480, 320), fill=(185, 177, 153))
        draw.rectangle((60, 70, 120, 205), fill=(70, 90, 105))
        draw.rectangle((210, 100, 275, 205), fill=(85, 105, 120))
        return img

    def test_bad_modern_assets_are_removed_before_counting_four(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in (
                "old-riyadh-souq.jpg",
                "railway-construction-1951.jpg",
                "riyadh-1975-construction.jpg",
            ):
                self._clear().save(root / name, "JPEG", quality=92)
            self._dusty().save(root / "riyadh-skyline.jpg", "JPEG", quality=92)
            index = root / "images.txt"
            index.write_text(
                "old-riyadh-souq.jpg | الرياض القديمة, old Riyadh, سوق تقليدي, الرياض | Historical archive\n"
                "railway-construction-1951.jpg | سكة حديد الرياض الدمام, 1951, Riyadh Dammam railway | archive\n"
                "riyadh-1975-construction.jpg | الرياض, 1975, البناء, السبعينات | archive\n"
                "riyadh-skyline.jpg | Riyadh skyline, الرياض | current\n",
                encoding="utf-8",
            )
            frames = [
                {"subject_kind": "place_city", "image_keywords": ["old Riyadh 1902"], "image_keywords_ar": ["الرياض القديمة", "1902"]},
                {"subject_kind": "place_city", "image_keywords": ["Riyadh Dammam railway 1951"], "image_keywords_ar": ["سكة حديد الرياض الدمام"]},
                {"subject_kind": "place_city", "image_keywords": ["Riyadh construction 1975"], "image_keywords_ar": ["الرياض البناء"]},
                {"subject_kind": "place_city", "image_keywords": ["Riyadh skyline"], "image_keywords_ar": ["أفق الرياض"]},
            ]
            old_dir, old_index = news_bot.IMAGES_DIR, news_bot.IMAGES_INDEX
            news_bot.IMAGES_DIR, news_bot.IMAGES_INDEX = root, index
            self.addCleanup(setattr, news_bot, "IMAGES_DIR", old_dir)
            self.addCleanup(setattr, news_bot, "IMAGES_INDEX", old_index)
            assignments = cvf.plan_reviewed_exact_assignments(
                frames, index, aliases=["Riyadh", "الرياض"]
            )

        names = {row["filename"] for row in assignments.values()}
        self.assertNotIn("riyadh-skyline.jpg", names)
        self.assertNotIn("old-riyadh-souq.jpg", names)
        self.assertEqual(2, len(assignments))

    def test_riyadh_pins_offer_alternates_for_human_repair(self):
        metro = cvf.pinned_riyadh_visuals({
            "subject_kind": "place_city",
            "heading": "الرياض تنزل تحت الأرض",
            "text": "افتتح مترو الرياض",
            "image_keywords": ["Riyadh Metro", "KAFD"],
            "image_keywords_ar": ["مترو الرياض"],
        })
        self.assertGreaterEqual(len(metro), 2)
        self.assertEqual("KAFD Station - Riyadh Metro.jpg", metro[0]["filename"])
        self.assertNotEqual(metro[0]["filename"], metro[1]["filename"])

        murabba = cvf.pinned_riyadh_visuals({
            "subject_kind": "place_city",
            "heading": "القصر الذي بُني خارج السور",
            "text": "بنى الملك عبدالعزيز قصر المربع خارج سور الرياض",
            "image_keywords": [],
            "image_keywords_ar": [],
        })
        self.assertTrue(murabba)
        self.assertEqual("Murabba Palace.jpg", murabba[0]["filename"])

    def test_pinned_visual_uses_reviewed_local_copy_before_network(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            local = root / "riyadh-skyline.jpg"
            self._clear().save(local, "JPEG", quality=92)
            out = root / "frame.jpg"
            asset = {
                "filename": "Riyadh Skyline.jpg",
                "commons_file": "Riyadh Skyline.jpg",
                "local_path": str(local),
                "credit": "reviewed",
            }
            sb = SimpleNamespace(_photo_digest=lambda _path: "digest", same_picture=lambda *_args: False)
            with patch.object(cvf.urllib.request, "urlopen", side_effect=AssertionError("network used")), \
                 patch.object(cvf.photo_quality, "has_poor_atmospheric_visibility", return_value=False):
                result = cvf._download_pinned_visual(asset, out, sb)

        self.assertEqual(str(out), result)


if __name__ == "__main__":
    unittest.main()
