import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image


class RiyadhStoryFormatContractTests(unittest.TestCase):
    def test_reference_geometry_matches_approved_riyadh_frames(self):
        import story_format

        self.assertEqual(story_format.FORMAT_ID, "riyadh-story-v1")
        self.assertEqual(story_format.CANVAS, (1080, 1920))
        self.assertEqual(story_format.MARGIN, 96)
        self.assertEqual(story_format.PHOTO_TOP, 420)
        self.assertEqual(story_format.PHOTO_ASPECT_HEIGHT, 0.72)
        self.assertEqual(story_format.PHOTO_RADIUS, 36)
        self.assertEqual(story_format.HEADER_RULE, (874, 170, 984, 180))
        self.assertEqual(story_format.KICKER_Y, 216)
        self.assertEqual(story_format.COUNTER_Y, 292)
        self.assertEqual(story_format.PHOTO_TEXT_GAP, 80)
        self.assertEqual(story_format.TITLE_SIZE, 60)
        self.assertEqual(story_format.BODY_SIZE, 42)

    def test_unapproved_story_format_is_rejected(self):
        import story_format

        with self.assertRaisesRegex(ValueError, "unsupported Story format"):
            story_format.require_story_format("another-layout")

    def test_sources_are_reserved_for_frame_six(self):
        source = Path("story_bot.py").read_text(encoding="utf-8")

        self.assertIn('last = n == total', source)
        self.assertIn('if last else None', source)
        self.assertIn('f"{n} / {total}"', source)

    def test_story_workflow_locks_the_reference_format(self):
        workflow = Path(".github/workflows/story.yml").read_text(encoding="utf-8")

        self.assertIn('STORY_FORMAT: "riyadh-story-v1"', workflow)
        self.assertIn('THEME: "light"', workflow)
        self.assertIn('FONT_FAMILY: "Almarai"', workflow)
        self.assertIn('STORY_FRAMES: "6"', workflow)

    def test_hormuz_reproduction_uses_shared_reference_format(self):
        source = Path("render_approved_hormuz_original.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("from story_format import", source)
        self.assertNotIn('TITLE_TOP = 1160', source)
        self.assertNotIn('TEXT_REGION = (72, 1110, 1008, 1680)', source)

    def test_hormuz_png_save_is_verified_and_atomic(self):
        from render_approved_hormuz_original import save_verified_png

        with TemporaryDirectory() as directory:
            output = Path(directory) / "frame.png"
            save_verified_png(Image.new("RGB", (1080, 1920), "white"), output)

            self.assertTrue(output.exists())
            self.assertFalse(output.with_suffix(".png.tmp").exists())
            with Image.open(output) as rendered:
                rendered.verify()


if __name__ == "__main__":
    unittest.main()
