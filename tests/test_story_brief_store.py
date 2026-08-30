import json
import os
import tempfile
import unittest
from pathlib import Path

import story_brief_store as sbs


class StoryBriefStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_root = os.environ.get("STORY_BRIEF_ROOT")
        os.environ["STORY_BRIEF_ROOT"] = self.tmp.name

    def tearDown(self):
        if self.old_root is None:
            os.environ.pop("STORY_BRIEF_ROOT", None)
        else:
            os.environ["STORY_BRIEF_ROOT"] = self.old_root
        self.tmp.cleanup()

    def test_revision_key_changes_with_prompt_model_or_frame_count(self):
        base = sbs.revision_key("قصة الرياض", "prompt-a", "claude-opus-5", 6)
        self.assertEqual(base, sbs.revision_key("قصة الرياض", "prompt-a", "claude-opus-5", 6))
        self.assertNotEqual(base, sbs.revision_key("قصة الرياض", "prompt-b", "claude-opus-5", 6))
        self.assertNotEqual(base, sbs.revision_key("قصة الرياض", "prompt-a", "other-model", 6))
        self.assertNotEqual(base, sbs.revision_key("قصة الرياض", "prompt-a", "claude-opus-5", 5))

    def test_locked_brief_round_trip_requires_matching_revision(self):
        payload = {"status": "EDITORIAL_LOCKED", "brief": {"frames": [{"heading": "h"}]}}
        path = sbs.save_locked_brief("قصة الرياض", "abc123", payload)
        self.assertTrue(path.exists())
        self.assertEqual(payload, sbs.load_locked_brief("قصة الرياض", "abc123"))
        self.assertIsNone(sbs.load_locked_brief("قصة الرياض", "different"))

    def test_only_locked_briefs_can_be_saved(self):
        with self.assertRaises(ValueError):
            sbs.save_locked_brief("story", "rev", {"status": "EDITORIAL_REVIEW"})

    def test_malformed_cache_fails_closed(self):
        path = sbs.brief_path("story", "rev")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not-json", encoding="utf-8")
        with self.assertRaises(sbs.BriefCacheError):
            sbs.load_locked_brief("story", "rev")

    def test_revision_mismatch_fails_closed(self):
        path = sbs.brief_path("story", "rev")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema": sbs.BRIEF_SCHEMA_VERSION,
            "revision": "other",
            "status": "EDITORIAL_LOCKED",
            "brief": {},
        }), encoding="utf-8")
        with self.assertRaises(sbs.BriefCacheError):
            sbs.load_locked_brief("story", "rev")

    def test_status_mismatch_fails_closed(self):
        path = sbs.brief_path("story", "rev")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema": sbs.BRIEF_SCHEMA_VERSION,
            "revision": "rev",
            "status": "EDITORIAL_REVIEW",
            "brief": {},
        }), encoding="utf-8")
        with self.assertRaises(sbs.BriefCacheError):
            sbs.load_locked_brief("story", "rev")


if __name__ == "__main__":
    unittest.main()
