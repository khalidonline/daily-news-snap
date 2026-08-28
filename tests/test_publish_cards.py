import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fake_news_bot():
    module = types.ModuleType("news_bot")
    module.CARDS_DIR = "cards"
    module.DRY_RUN = False
    module.POST_PROVIDER = "bundle"
    module.MEDIA_MODE = "github"
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
    def test_bundle_keeps_each_reviewed_frame_as_separate_upload(self):
        frames = ["card-1.png", "card-2.png", "card-3.png", "card-4.png"]
        with patch.object(publish_cards, "POST_PROVIDER", "bundle"), \
             patch.object(publish_cards, "frames_to_video") as to_video:
            media = publish_cards.prepare_publish_media(frames, "2026-08-28-2pm")

        self.assertEqual(media, frames)
        to_video.assert_not_called()

    def test_non_bundle_still_uses_video_for_multi_frame_story(self):
        frames = ["card-1.png", "card-2.png"]
        with patch.object(publish_cards, "POST_PROVIDER", "zernio"), \
             patch.object(publish_cards, "frames_to_video", return_value="story.mp4") as to_video:
            media = publish_cards.prepare_publish_media(frames, "2026-08-28-2pm")

        self.assertEqual(media, ["story.mp4"])
        to_video.assert_called_once()


if __name__ == "__main__":
    unittest.main()
