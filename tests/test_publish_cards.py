import importlib
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

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


class PublishMediaTests(unittest.TestCase):
    def test_bundle_submits_one_verified_video_post(self):
        frames = ["card-1.png", "card-2.png", "card-3.png"]
        scheduled = {"id": "post-123", "status": "SCHEDULED"}
        posted = {"id": "post-123", "status": "POSTED"}

        with patch.object(publish_cards, "frames_to_video", return_value="story.mp4") as to_video, \
             patch.object(publish_cards, "validate_story_video", return_value=True) as validate, \
             patch.object(publish_cards, "post_story", return_value=scheduled) as post_story, \
             patch.object(publish_cards, "wait_for_bundle_post", return_value=posted) as wait_post:
            result = publish_cards.publish_bundle_story("caption", frames, "2026-08-28-2pm")

        self.assertEqual(result, posted)
        to_video.assert_called_once_with(
            frames, Path(publish_cards.CARDS_DIR) / "2026-08-28-2pm-story.mp4"
        )
        validate.assert_called_once_with("story.mp4", frames)
        post_story.assert_called_once_with("caption", [], ["story.mp4"])
        wait_post.assert_called_once_with(scheduled)

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

    def test_latest_real_story_deck_builds_and_validates_as_one_video(self):
        stamp, frames = publish_cards.find_story("")
        self.assertTrue(stamp)
        self.assertGreaterEqual(len(frames), 2)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / f"{stamp}-story.mp4"
            video = publish_cards.frames_to_video(frames, out)
            self.assertTrue(Path(video).exists())
            self.assertTrue(publish_cards.validate_story_video(video, frames))

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
