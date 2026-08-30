import os
import tempfile
import unittest
from pathlib import Path

import story_notification_state as sns


class NotificationStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("STORY_NOTIFICATION_LEDGER")
        os.environ["STORY_NOTIFICATION_LEDGER"] = str(Path(self.tmp.name) / "notifications.jsonl")
        self.frames = []
        for name, data in (("1.png", b"one"), ("2.png", b"two")):
            path = Path(self.tmp.name) / name
            path.write_bytes(data)
            self.frames.append(path)

    def tearDown(self):
        if self.old is None:
            os.environ.pop("STORY_NOTIFICATION_LEDGER", None)
        else:
            os.environ["STORY_NOTIFICATION_LEDGER"] = self.old
        self.tmp.cleanup()

    def test_deck_hash_is_order_sensitive(self):
        first = sns.deck_hash(self.frames)
        second = sns.deck_hash(list(reversed(self.frames)))
        self.assertNotEqual(first, second)
        self.assertEqual(first, sns.deck_hash(self.frames))

    def test_only_ready_and_review_are_notifiable(self):
        self.assertTrue(sns.should_notify("READY"))
        self.assertTrue(sns.should_notify("REVIEW"))
        self.assertFalse(sns.should_notify("BLOCKED"))
        self.assertFalse(sns.should_notify("VISUAL_ASSEMBLY"))

    def test_same_deck_can_be_claimed_only_once(self):
        digest = sns.deck_hash(self.frames)
        claim = sns.claim_notification("story", "rev", "READY", digest)
        self.assertIsNotNone(claim)
        self.assertIsNone(sns.claim_notification("story", "rev", "READY", digest))
        sns.complete_notification(claim, "story", "rev", "READY", digest)
        self.assertTrue(sns.notification_ledger_path().exists())

    def test_changed_deck_gets_new_claim(self):
        first = sns.deck_hash(self.frames)
        claim1 = sns.claim_notification("story", "rev", "REVIEW", first)
        self.assertIsNotNone(claim1)
        self.frames[1].write_bytes(b"changed")
        second = sns.deck_hash(self.frames)
        claim2 = sns.claim_notification("story", "rev", "REVIEW", second)
        self.assertIsNotNone(claim2)

    def test_failed_send_can_release_claim_for_retry(self):
        digest = sns.deck_hash(self.frames)
        claim = sns.claim_notification("story", "rev", "READY", digest)
        sns.release_notification(claim)
        self.assertIsNotNone(sns.claim_notification("story", "rev", "READY", digest))


if __name__ == "__main__":
    unittest.main()
