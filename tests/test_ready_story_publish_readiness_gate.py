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

    def test_locked_editorial_requires_valid_locked_cache(self):
        story = "Story A"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            story_dir = root / prp._story_id(story)
            story_dir.mkdir(parents=True)
            (story_dir / "draft.json").write_text(
                json.dumps({
                    "schema": "story-brief-v1",
                    "revision": "draft",
                    "status": "DRAFT",
                    "brief": {},
                }),
                encoding="utf-8",
            )
            self.assertFalse(prp.has_locked_editorial(story, brief_root=root))
            (story_dir / "locked.json").write_text(
                json.dumps({
                    "schema": "story-brief-v1",
                    "revision": "locked",
                    "status": "EDITORIAL_LOCKED",
                    "brief": {"frames": []},
                }),
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
                "revision": revision,
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

    def test_ready_pool_workflows_use_publication_evidence_builder(self):
        workflows = [
            Path(".github/workflows/ready-story-pool.yml"),
            Path(".github/workflows/targeted-near-pass-repair.yml"),
            Path(".github/workflows/targeted-logo-repair.yml"),
        ]
        for workflow in workflows:
            text = workflow.read_text(encoding="utf-8")
            self.assertIn("python publication_ready_pool.py", text, str(workflow))
            self.assertNotIn("ready_story_publish.py --refresh-only", text, str(workflow))

    def test_ready_pool_refresh_never_rewrites_workflow_files(self):
        text = Path(".github/workflows/ready-story-pool.yml").read_text(encoding="utf-8")
        self.assertIn("git add state/ready_to_post.json", text)
        self.assertNotIn("git add state/ready_to_post.json .github/workflows/story.yml", text)
        self.assertNotIn("git worktree", text)
        self.assertNotIn("/tmp/story-main", text)
        self.assertNotIn("Sync READY choices into repair workflow", text)
        self.assertNotIn("Sync READY choices to live workflow on main", text)


if __name__ == "__main__":
    unittest.main()
