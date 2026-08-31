import json
import tempfile
import unittest
from pathlib import Path

import publication_ready_pool as prp


class PublicationReadyPoolTests(unittest.TestCase):
    def test_visual_pass_without_publication_evidence_is_not_ready(self):
        stories = ["visual-only", "publication-ready"]
        coverage = {
            "visual-only": (list(range(4)), ["logo"], "PASS"),
            "publication-ready": (list(range(4)), ["logo"], "PASS"),
        }

        ready = prp.collect_publication_ready_stories(
            stories,
            coverage_fn=lambda story: coverage[story],
            evidence_fn=lambda story: story == "publication-ready",
        )

        self.assertEqual(["publication-ready"], ready)

    def test_non_visual_pass_never_becomes_ready_even_with_publication_evidence(self):
        ready = prp.collect_publication_ready_stories(
            ["needs-photo"],
            coverage_fn=lambda _story: (list(range(3)), ["logo"], "NEEDS 1 MORE PHOTO"),
            evidence_fn=lambda _story: True,
        )

        self.assertEqual([], ready)

    def test_locked_editorial_requires_matching_story_and_locked_status(self):
        story = "Story A"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            story_dir = root / prp._story_id(story)
            story_dir.mkdir(parents=True)
            (story_dir / "draft.json").write_text(
                json.dumps({"status": "DRAFT", "story": story, "brief": {}}),
                encoding="utf-8",
            )
            self.assertFalse(prp.has_locked_editorial(story, brief_root=root))
            (story_dir / "locked.json").write_text(
                json.dumps({"status": "EDITORIAL_LOCKED", "story": story, "brief": {"frames": []}}),
                encoding="utf-8",
            )
            self.assertTrue(prp.has_locked_editorial(story, brief_root=root))

    def test_rendered_state_requires_six_pass_frames(self):
        story = "Story A"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            revision = "rev"
            state_dir = root / prp._story_id(story) / revision
            state_dir.mkdir(parents=True)
            payload = {
                "schema": "story-visual-v1",
                "story": story,
                "status": "VISUAL_READY",
                "frames": {str(i): {"status": "PASS"} for i in range(1, 7)},
            }
            (state_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(
                prp.has_complete_rendered_state(story, visual_root=root, expected_frames=6)
            )
            payload["frames"]["6"]["status"] = "FAIL"
            (state_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(
                prp.has_complete_rendered_state(story, visual_root=root, expected_frames=6)
            )


if __name__ == "__main__":
    unittest.main()
