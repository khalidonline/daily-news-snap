import tempfile
import unittest
from pathlib import Path

from PIL import Image

from review_visual_gate import is_photographic_frame


class RepairAlibabaFrame3Tests(unittest.TestCase):
    def test_repair_renders_frame_three_with_a_real_photo(self):
        from repair_alibaba_frame3 import repair_frame

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame = root / "frame-03.png"
            photo = root / "jack-ma-1995.jpg"
            source = Image.new("RGB", (900, 700))
            pixels = source.load()
            for y in range(source.height):
                for x in range(source.width):
                    pixels[x, y] = ((x * 17 + y * 3) % 256, (x * 5 + y * 11) % 256, (x + y * 19) % 256)
            source.save(photo)

            repair_frame(frame, photo)

            with Image.open(frame) as rendered:
                rendered.load()
                self.assertEqual(rendered.size, (1080, 1920))
            self.assertTrue(is_photographic_frame(frame))


if __name__ == "__main__":
    unittest.main()
