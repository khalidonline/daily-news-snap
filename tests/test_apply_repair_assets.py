import unittest

from PIL import Image

import tools.apply_repair_assets as ara


class RepairAssetCropTests(unittest.TestCase):
    def test_relative_crop_box_extracts_left_photo_panel(self):
        self.assertTrue(
            hasattr(ara, "crop_from_spec"),
            "manifest crop support is not implemented yet",
        )
        img = Image.new("RGB", (1200, 500), "white")
        cropped = ara.crop_from_spec(img, {"crop_box": [0.0, 0.0, 0.28, 1.0]})
        self.assertEqual(cropped.size, (336, 500))

    def test_missing_crop_box_leaves_image_unchanged(self):
        self.assertTrue(hasattr(ara, "crop_from_spec"))
        img = Image.new("RGB", (640, 480), "white")
        self.assertIs(ara.crop_from_spec(img, {}), img)


if __name__ == "__main__":
    unittest.main()
