import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import call, patch

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fake_news_bot():
    module = types.ModuleType("news_bot")
    module.CARDS_DIR = "cards"
    module.DRY_RUN = False
    module.POST_PROVIDER = "bundle"
    module.MEDIA_MODE = "github"
    module.BUNDLE_API_KEY = "test-key"
    module.BUNDLE_BASE = "https://api.bundle.social/api/v1"
    module.BUNDLE_HEADERS = {"User-Agent": "test"}
    module.post_story = lambda *args, **kwargs: {}
    module.post_ok = lambda response: True
    module.describe_failure = lambda response: ""
    module.quota_ok = lambda: True
    module.quota_bump = lambda: None
    module.commit_and_push = lambda *args, **kwargs: None
    module.notify = lambda *args, **kwargs: None
    module.notify_album = lambda *args, **kwargs: None
    module.ksa_stamp = lambda: "test"
    module.deliver_unposted = lambda *args, **kwargs: None
    module.publish_many_via_github = lambda media: []
    module.upload_media = lambda path: ""
    return module


sys.modules.setdefault("news_bot", _fake_news_bot())
review_visual_gate = importlib.import_module("review_visual_gate")
safe_publish_cards = importlib.import_module("safe_publish_cards")


def _photo(path, seed):
    img = Image.new("RGB", (900, 650), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    for y in range(0, 650, 8):
        for x in range(0, 900, 8):
            v = (x * (11 + seed) + y * (17 + seed)) % 256
            draw.rectangle((x, y, x + 7, y + 7), fill=(v, (v * 3) % 256, (v * 7) % 256))
    img.save(path)


def _logo(path):
    img = Image.new("RGB", (500, 240), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((80, 60, 420, 180), fill=(15, 70, 120))
    img.save(path)


class SimpleReviewTests(unittest.TestCase):
    def test_standard_four_picture_coverage_is_applied_to_rendered_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = []
            for i in range(6):
                path = root / f"frame-{i+1}.png"
                Image.new("RGB", (1080, 1920), (238, 232, 227)).save(path)
                frames.append(str(path))
            photos = []
            for i in range(4):
                path = root / f"photo-{i+1}.jpg"
                _photo(path, i + 1)
                photos.append(str(path))

            count = review_visual_gate.apply_requested_photos(frames, photos, requested=4)

            self.assertEqual(count, 4)
            self.assertEqual(
                sum(review_visual_gate.is_photographic_frame(f) for f in frames),
                4,
            )

    def test_remaining_cards_repeat_same_logo_after_four_photos(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = []
            for i in range(6):
                path = root / f"frame-{i+1}.png"
                Image.new("RGB", (1080, 1920), (238, 232, 227)).save(path)
                frames.append(str(path))
            photos = []
            for i in range(4):
                path = root / f"photo-{i+1}.jpg"
                _photo(path, i + 1)
                photos.append(str(path))
            logo = root / "logo.png"
            _logo(logo)

            review_visual_gate.apply_requested_photos(frames, photos, requested=4)
            filled = review_visual_gate.apply_fallback_visuals(
                frames, [str(logo)], start_index=4
            )

            self.assertEqual(filled, 2)
            for frame in frames[4:]:
                image = Image.open(frame).convert("RGB")
                box = review_visual_gate._pixel_box(image)
                crop = image.crop(box)
                self.assertNotEqual(crop.getbbox(), None)
                self.assertNotEqual(crop.getpixel((crop.width // 2, crop.height // 2)), (238, 232, 227))

    def test_review_builds_one_fresh_story_with_automatic_picture_standard(self):
        fresh = [f"fresh-{i}.png" for i in range(1, 7)]
        approved = [f"approved-{i}.jpg" for i in range(1, 5)]
        logos = ["approved-logo.png"]
        with patch.object(safe_publish_cards, "_build_fresh_review_story", return_value=("2026-08-28-8pm", fresh)) as build, \
             patch.object(safe_publish_cards, "_story_identity", return_value="Jack Bogle: canonical") as identity, \
             patch.object(safe_publish_cards, "approved_runtime_visuals", return_value=(approved, logos)) as visuals, \
             patch.object(safe_publish_cards, "apply_requested_photos", return_value=4) as apply_photos, \
             patch.object(safe_publish_cards, "apply_fallback_visuals", return_value=2) as apply_fallback, \
             patch.object(safe_publish_cards, "require_photo_coverage", return_value=4) as gate, \
             patch.object(safe_publish_cards.publisher, "load_caption", return_value="caption"), \
             patch.object(safe_publish_cards, "_telegram_review_photo", return_value=True) as send_photo:
            safe_publish_cards.review_story_on_telegram("Jack Bogle")

        build.assert_called_once_with("Jack Bogle")
        identity.assert_called_once_with("2026-08-28-8pm")
        visuals.assert_called_once_with("Jack Bogle: canonical")
        apply_photos.assert_called_once_with(fresh, approved, requested=4)
        apply_fallback.assert_called_once_with(fresh, logos, start_index=4)
        gate.assert_called_once_with(fresh, minimum=4)
        self.assertEqual(send_photo.call_count, 6)
        self.assertEqual(
            send_photo.call_args_list[0],
            call("👀 مراجعة قبل النشر — 2026-08-28-8pm\n1/6\ncaption", "fresh-1.png"),
        )

    def test_review_requires_only_story(self):
        with self.assertRaises(SystemExit):
            safe_publish_cards.review_story_on_telegram("")


if __name__ == "__main__":
    unittest.main()
