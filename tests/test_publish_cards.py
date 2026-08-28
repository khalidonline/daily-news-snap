import importlib
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import call, patch

import imageio_ffmpeg
from PIL import Image


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
publish_cards = importlib.import_module("publish_cards")
safe_publish_cards = importlib.import_module("safe_publish_cards")


class PublishMediaTests(unittest.TestCase):
    def test_bundle_refuses_multi_frame_deck_before_live_publish(self):
        frames = ["card-1.png", "card-2.png", "card-3.png"]
        with self.assertRaises(SystemExit) as exc:
            safe_publish_cards.guard_bundle_multiframe("bundle", frames, dry_run=False)
        self.assertIn("cannot publish 3 separate Snapchat Story photos", str(exc.exception))

    def test_bundle_guard_allows_dry_run(self):
        safe_publish_cards.guard_bundle_multiframe(
            "bundle", ["card-1.png", "card-2.png"], dry_run=True
        )

    def test_telegram_review_sends_each_frame_as_separate_verified_photo(self):
        frames = ["card-1.png", "card-2.png", "card-3.png"]
        with patch.object(safe_publish_cards.publisher, "resolve_story_selector", return_value="2026-08-28-2pm"), \
             patch.object(safe_publish_cards.publisher, "find_story", return_value=("2026-08-28-2pm", frames)), \
             patch.object(safe_publish_cards.publisher, "load_caption", return_value="review caption"), \
             patch.object(safe_publish_cards, "_telegram_review_photo", return_value=True) as send_photo, \
             patch.object(safe_publish_cards.publisher, "notify_album") as notify_album, \
             patch.object(safe_publish_cards.publisher, "main") as public_publish:
            safe_publish_cards.run_mode("telegram_review")

        self.assertEqual(send_photo.call_count, 3)
        send_photo.assert_has_calls([
            call("👀 مراجعة قبل النشر — 2026-08-28-2pm\n1/3\nreview caption", "card-1.png"),
            call("👀 مراجعة قبل النشر — 2026-08-28-2pm\n2/3", "card-2.png"),
            call("👀 مراجعة قبل النشر — 2026-08-28-2pm\n3/3", "card-3.png"),
        ])
        notify_album.assert_not_called()
        public_publish.assert_not_called()

    def test_telegram_review_fails_if_any_photo_is_not_confirmed(self):
        frames = ["card-1.png", "card-2.png", "card-3.png"]
        with patch.object(safe_publish_cards.publisher, "resolve_story_selector", return_value="2026-08-28-2pm"), \
             patch.object(safe_publish_cards.publisher, "find_story", return_value=("2026-08-28-2pm", frames)), \
             patch.object(safe_publish_cards.publisher, "load_caption", return_value="review caption"), \
             patch.object(safe_publish_cards, "_telegram_review_photo", side_effect=[True, False, True]):
            with self.assertRaises(SystemExit) as exc:
                safe_publish_cards.run_mode("telegram_review")
        self.assertIn("Telegram confirmed only 1/3 review photos", str(exc.exception))

    def test_frames_to_video_contains_every_source_frame_in_order(self):
        colors = [
            (230, 20, 20),
            (20, 220, 20),
            (20, 20, 230),
            (220, 220, 20),
            (220, 20, 220),
            (20, 220, 220),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = []
            for index, color in enumerate(colors, start=1):
                path = root / f"frame-{index}.png"
                Image.new("RGB", (108, 192), color).save(path)
                frames.append(str(path))

            out = root / "story.mp4"
            with patch.object(publish_cards, "FRAME_SECONDS", 2), \
                 patch.object(publish_cards, "TAIL_MARGIN", 0):
                publish_cards.frames_to_video(frames, out)

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            for index, (second, expected) in enumerate(zip((1, 3, 5, 7, 9, 11), colors), start=1):
                sample = root / f"sample-{index}.png"
                subprocess.run(
                    [ffmpeg, "-y", "-loglevel", "error", "-ss", str(second),
                     "-i", str(out), "-frames:v", "1", str(sample)],
                    check=True,
                )
                actual = Image.open(sample).convert("RGB").getpixel((540, 960))
                self.assertLess(
                    max(abs(a - b) for a, b in zip(actual, expected)),
                    35,
                    f"video segment {index} did not match source frame {index}: {actual} vs {expected}",
                )

    def test_non_bundle_still_uses_video_for_multi_frame_story(self):
        frames = ["card-1.png", "card-2.png"]
        with patch.object(publish_cards, "POST_PROVIDER", "zernio"), \
             patch.object(publish_cards, "frames_to_video", return_value="story.mp4") as to_video:
            media = publish_cards.prepare_publish_media(frames, "2026-08-28-2pm")

        self.assertEqual(media, ["story.mp4"])
        to_video.assert_called_once()


class StorySelectorTests(unittest.TestCase):
    def _write_sidecar(self, root, stamp, **data):
        Path(root, f"{stamp}-story.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_partial_arabic_story_name_resolves_unique_built_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_sidecar(tmp, "2026-08-25-2pm", title="قصة سليمان الراجحي")
            self._write_sidecar(tmp, "2026-08-26-2pm", title="قصة جاك بوغل")
            with patch.object(publish_cards, "CARDS_DIR", tmp):
                stamp = publish_cards.resolve_story_selector("سليمان")
        self.assertEqual(stamp, "2026-08-25-2pm")

    def test_ambiguous_partial_name_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_sidecar(tmp, "2026-08-24-2pm", title="سليمان الراجحي")
            self._write_sidecar(tmp, "2026-08-25-2pm", title="صالح الراجحي")
            with patch.object(publish_cards, "CARDS_DIR", tmp):
                with self.assertRaises(SystemExit) as exc:
                    publish_cards.resolve_story_selector("الراجحي")
        self.assertIn("multiple built stories match", str(exc.exception))

    def test_timestamp_selector_is_preserved(self):
        self.assertEqual(
            publish_cards.resolve_story_selector("2026-08-26-2pm"),
            "2026-08-26-2pm",
        )


if __name__ == "__main__":
    unittest.main()
