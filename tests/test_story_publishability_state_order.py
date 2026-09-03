import json
import os
import tempfile
import unittest
from pathlib import Path

import story_publishability as sp


class StoryPublishabilityStateOrderTests(unittest.TestCase):
    def test_latest_state_uses_evaluation_timestamp_not_checkout_mtime(self):
        story = "story-a"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            parent = root / sp._story_id(story)
            older = parent / "zzzz-old" / "state.json"
            newer = parent / "aaaa-new" / "state.json"
            older.parent.mkdir(parents=True)
            newer.parent.mkdir(parents=True)
            older.write_text(json.dumps({
                "story": story,
                "publishability_policy": sp.PUBLISHABILITY_POLICY,
                "publishability_evaluated_at": "2026-09-01T00:00:00+00:00",
                "frames": {},
            }), encoding="utf-8")
            newer.write_text(json.dumps({
                "story": story,
                "publishability_policy": sp.PUBLISHABILITY_POLICY,
                "publishability_evaluated_at": "2026-09-03T00:00:00+00:00",
                "frames": {},
            }), encoding="utf-8")
            # Simulate a Git checkout where both files receive the same mtime.
            os.utime(older, ns=(1_000_000_000, 1_000_000_000))
            os.utime(newer, ns=(1_000_000_000, 1_000_000_000))
            revision, state = sp.latest_visual_state(story, root=root)
            self.assertEqual(revision, "aaaa-new")
            self.assertEqual(
                state["publishability_evaluated_at"],
                "2026-09-03T00:00:00+00:00",
            )


if __name__ == "__main__":
    unittest.main()
