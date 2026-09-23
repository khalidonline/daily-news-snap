import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
import story_bot as story


class StoryFooterTests(unittest.TestCase):
    def test_crowded_card_keeps_all_text_above_closing_seal(self):
        original_text = ImageDraw.ImageDraw.text
        text_bottoms = []
        def record(draw, xy, text, *args, **kwargs):
            if kwargs.get("anchor") == "ma" and kwargs.get("fill") in (story.ACCENT, story.TEXT, story.BODY):
                box = draw.textbbox(xy, text, font=kwargs.get("font"), anchor=kwargs.get("anchor"),
                                    **{k: kwargs[k] for k in ("direction", "language", "features") if k in kwargs})
                text_bottoms.append(box[3])
            return original_text(draw, xy, text, *args, **kwargs)
        original = story.closing_seal
        inspected = []
        def inspect(image, centre_y):
            # Inspect actual rendered pixels before the seal can hide them.
            bottom = centre_y - 60 - 36
            self.assertTrue(text_bottoms)
            self.assertLessEqual(max(text_bottoms), bottom)
            text_bottoms.clear()
            inspected.append(True)
            original(image, centre_y)
        with tempfile.TemporaryDirectory() as tmp:
            photo = Path(tmp) / 'photo.png'
            Image.new('RGB', (1080, 800), (110, 150, 180)).save(photo)
            for footer in (None, 'المصادر: الموقع الرسمي'):
                with self.subTest(footer=footer), patch.object(story, 'closing_seal', side_effect=inspect), patch.object(ImageDraw.ImageDraw, 'text', record):
                    story.render_frame(Path(tmp) / 'card.png', 'ملخص تنفيذي', '1 من 3',
                        'حكاية مكان صار جزء من يوم الناس', 64,
                        sub='بدأ المكان بفكرة بسيطة، ومع الوقت صار الناس يجتمعون فيه ويتناقلون قصته. ' * 7,
                        photo=photo, punch='كل تغيير صغير يترك أثره في قصة المكان والناس', footer=footer)
        self.assertEqual(len(inspected), 2)

    def test_unrenderable_text_does_not_save_an_overlapped_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'card.png'
            with self.assertRaises(ValueError):
                story.render_frame(target, 'ملخص تنفيذي', '1 من 1', 'قصة المكان', 64,
                                   sub='هذه قصة طويلة تحتاج مساحة واضحة للقراءة. ' * 300,
                                   punch='الخلاصة واضحة')
            self.assertFalse(target.exists())

    def test_photo_caption_is_below_image_without_changing_brand_or_footer(self):
        from PIL import ImageChops
        with tempfile.TemporaryDirectory() as tmp:
            photo = Path(tmp) / 'photo.png'
            Image.new('RGB', (1080, 800), (110, 150, 180)).save(photo)
            plain, captioned = Path(tmp)/'plain.png', Path(tmp)/'captioned.png'
            options = dict(photo=photo, sub='بدأ السباقات وهو صغير.', footer='المصادر: الموقع الرسمي')
            story.render_frame(plain, 'ملخص تنفيذي', '1 من 3', 'بداية القصة', 60, **options)
            story.render_frame(captioned, 'ملخص تنفيذي', '1 من 3', 'بداية القصة', 60,
                               photo_caption='صورة توضيحية للكارتينج', **options)
            difference = ImageChops.difference(Image.open(plain), Image.open(captioned))
            box = difference.getbbox()
            self.assertIsNotNone(box)
            self.assertGreaterEqual(box[1], 1059)
            self.assertLess(box[3], 1139)
