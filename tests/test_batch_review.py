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
batch_review = importlib.import_module("batch_review")


class BatchReviewTests(unittest.TestCase):
    def test_batch_validates_remaining_stories_and_sends_one_text_summary(self):
        stories = ["Story A", "Jack Bogle story", "Story B"]
        with patch.object(batch_review, "validate_story", side_effect=[
            (True, "4/6 photos"),
            (False, "only 3 approved photos"),
        ]) as validate, patch.object(batch_review, "send_summary") as send_summary:
            results = batch_review.run_batch(
                stories=stories,
                already_ready={"Jack Bogle story"},
            )

        self.assertEqual(validate.call_count, 2)
        self.assertEqual([r[0] for r in results], ["Story A", "Story B"])
        send_summary.assert_called_once()
        summary = send_summary.call_args.args[0]
        self.assertIn("PASS", summary)
        self.assertIn("FAIL", summary)
        self.assertIn("1/2 ready", summary)

    def test_repaired_story_set_has_25_and_bogle_is_excluded_from_batch(self):
        self.assertEqual(len(batch_review.REPAIRED_STORIES), 25)
        remaining = batch_review.remaining_repaired_stories()
        self.assertEqual(len(remaining), 24)
        self.assertFalse(any("Jack Bogle" in story for story in remaining))


if __name__ == "__main__":
    unittest.main()
