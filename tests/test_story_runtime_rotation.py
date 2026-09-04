import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import story_runtime as sr


class StoryRuntimeRotationTests(unittest.TestCase):
    def test_telegram_reviewed_story_is_not_a_fresh_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "story_notifications.jsonl"
            ledger.write_text(
                json.dumps({"event": "telegram_sent", "story": "already reviewed"}) + "\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"STORY_NOTIFICATION_LEDGER": str(ledger)}), \
                 patch.object(sr.sb, "load_stories", return_value=["already reviewed", "fresh"]), \
                 patch.object(sr.sb, "load_used", return_value=[]), \
                 patch.object(sr.sb, "load_skipped", return_value=[]), \
                 patch.object(sr.sb, "_UNIDENTIFIED", set()), \
                 patch.dict(sr.sb._STORY_POOLS, {"already reviewed": "general", "fresh": "general"}, clear=True):
                self.assertEqual(sr._fresh_candidates("general"), ["fresh"])


if __name__ == "__main__":
    unittest.main()
