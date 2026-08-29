import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

import photo_quality
import news_bot


class GlobalPhotoQualityTests(unittest.TestCase):
    def _save(self, image, name):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        path = Path(td.name) / name
        image.save(path, "JPEG", quality=92)
        return path

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
        for x, h, shade in ((40, 90, 70), (115, 125, 105), (205, 72, 55), (290, 145, 95), (390, 110, 75)):
            draw.rectangle((x, 205 - h, x + 35, 205), fill=(shade, shade + 15, shade + 22))
        return img

    def test_heavy_dust_orange_atmospheric_cast_is_rejected(self):
        path = self._save(self._dusty(), "dusty-city.jpg")
        self.assertTrue(photo_quality.has_poor_atmospheric_visibility(path))

    def test_clear_outdoor_photo_is_not_rejected(self):
        path = self._save(self._clear(), "clear-city.jpg")
        self.assertFalse(photo_quality.has_poor_atmospheric_visibility(path))

    def test_varied_black_and_white_archive_photo_is_not_rejected(self):
        img = Image.new("L", (480, 320), 190)
        draw = ImageDraw.Draw(img)
        for x in range(0, 480, 40):
            shade = 45 + (x // 40) * 14
            draw.rectangle((x, 80, x + 28, 270), fill=shade)
        draw.rectangle((0, 270, 480, 320), fill=95)
        path = self._save(img.convert("RGB"), "archive-bw.jpg")
        self.assertFalse(photo_quality.has_poor_atmospheric_visibility(path))

    def test_shared_download_sanity_rejects_dusty_photo(self):
        path = self._save(self._dusty(), "dusty-download.jpg")
        self.assertTrue(news_bot.looks_like_a_graphic(path))

    def test_local_library_skips_dusty_match_and_uses_clear_alternative(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dusty = root / "dusty.jpg"
            clear = root / "clear.jpg"
            self._dusty().save(dusty, "JPEG", quality=92)
            self._clear().save(clear, "JPEG", quality=92)
            index = root / "images.txt"
            index.write_text(
                "dusty.jpg | Riyadh skyline, الرياض | archive\n"
                "clear.jpg | Riyadh skyline, الرياض | archive\n",
                encoding="utf-8",
            )
            old_dir, old_index = news_bot.IMAGES_DIR, news_bot.IMAGES_INDEX
            news_bot.IMAGES_DIR, news_bot.IMAGES_INDEX = root, index
            self.addCleanup(setattr, news_bot, "IMAGES_DIR", old_dir)
            self.addCleanup(setattr, news_bot, "IMAGES_INDEX", old_index)
            out = root / "selected.jpg"
            selected, _credit = news_bot.fetch_local_photo(
                [], ["Riyadh skyline"], out, respect_cooldown=False
            )
            self.assertIsNotNone(selected)
            marker = Path(str(out) + ".exempt").read_text(encoding="utf-8")
            self.assertEqual("local:clear.jpg", marker)

    def test_warm_historical_archive_is_not_treated_as_modern_dust(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "old-riyadh-souq.jpg"
            self._dusty().save(archive, "JPEG", quality=92)
            index = root / "images.txt"
            index.write_text(
                "old-riyadh-souq.jpg | الرياض القديمة, old Riyadh, سوق تقليدي | Historical archive\n",
                encoding="utf-8",
            )
            old_dir, old_index = news_bot.IMAGES_DIR, news_bot.IMAGES_INDEX
            news_bot.IMAGES_DIR, news_bot.IMAGES_INDEX = root, index
            self.addCleanup(setattr, news_bot, "IMAGES_DIR", old_dir)
            self.addCleanup(setattr, news_bot, "IMAGES_INDEX", old_index)
            out = root / "selected.jpg"
            selected, _credit = news_bot.fetch_local_photo(
                [], ["old Riyadh"], out, respect_cooldown=False
            )
            self.assertIsNotNone(selected)
            marker = Path(str(out) + ".exempt").read_text(encoding="utf-8")
            self.assertEqual("local:old-riyadh-souq.jpg", marker)


if __name__ == "__main__":
    unittest.main()
