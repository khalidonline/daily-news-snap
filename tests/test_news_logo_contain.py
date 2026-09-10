import inspect
import unittest

from PIL import Image, ImageDraw

import news_bot


class NewsLogoContainTests(unittest.TestCase):
    def test_organization_logo_is_contained_without_cropping(self):
        logo = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
        draw = ImageDraw.Draw(logo)
        draw.rectangle((20, 20, 280, 80), fill=(0, 0, 0, 255))

        fitted = news_bot.fit_card_visual(
            logo,
            300,
            300,
            fit_mode="contain",
            background=(238, 232, 227),
        )

        self.assertEqual(fitted.size, (300, 300))
        self.assertEqual(fitted.getpixel((0, 0)), (238, 232, 227))
        self.assertEqual(fitted.getpixel((150, 150)), (0, 0, 0))
        self.assertEqual(fitted.getpixel((150, 40)), (238, 232, 227))

    def test_news_main_requests_contain_for_explicit_organization_logo(self):
        source = inspect.getsource(news_bot.main)
        self.assertIn('recovery_visual_kind") == "organization_logo"', source)
        self.assertIn("photo_fit=visual_fit", source)


if __name__ == "__main__":
    unittest.main()
