import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

import photo_quality


class GlobalPhotoQualityTests(unittest.TestCase):
    def _save(self, image, name):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        path = Path(td.name) / name
        image.save(path, "JPEG", quality=92)
        return path

    def test_heavy_dust_orange_atmospheric_cast_is_rejected(self):
        img = Image.new("RGB", (480, 320), (224, 151, 91))
        draw = ImageDraw.Draw(img)
        # A low-visibility city silhouette under a strong sand/orange cast,
        # matching the visual failure seen on Riyadh Story #93 frame 6.
        for x, h in ((35, 65), (90, 100), (155, 72), (220, 125), (300, 88), (380, 110)):
            draw.rectangle((x, 250 - h, x + 32, 250), fill=(126, 99, 78))
        draw.rectangle((0, 250, 480, 320), fill=(171, 121, 82))
        path = self._save(img, "dusty-city.jpg")
        self.assertTrue(photo_quality.has_poor_atmospheric_visibility(path))

    def test_clear_outdoor_photo_is_not_rejected(self):
        img = Image.new("RGB", (480, 320), (103, 178, 226))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 205, 480, 320), fill=(185, 177, 153))
        for x, h, shade in ((40, 90, 70), (115, 125, 105), (205, 72, 55), (290, 145, 95), (390, 110, 75)):
            draw.rectangle((x, 205 - h, x + 35, 205), fill=(shade, shade + 15, shade + 22))
        path = self._save(img, "clear-city.jpg")
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


if __name__ == "__main__":
    unittest.main()
