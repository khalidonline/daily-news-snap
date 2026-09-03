import tempfile
import unittest
from pathlib import Path

import revalidate_story_pool as rsp
import story_publishability as sp


class StoryPoolRevalidationTests(unittest.TestCase):
    def _state(self, root: Path, story="story-a"):
        revision = "rev-a"
        assets = root / sp._story_id(story) / revision / "assets"
        assets.mkdir(parents=True)
        frames = {}
        for i in range(1, 7):
            photo = assets / f"frame-{i:02d}.jpg"
            photo.write_bytes(f"frame-{i}".encode())
            frames[str(i)] = {
                "status": "PASS",
                "image_source": str(photo),
                "frame_payload": {
                    "heading": f"heading {i}",
                    "text": f"text {i}",
                },
            }
        return revision, {"story": story, "revision": revision, "frames": frames}

    def test_revalidation_marks_unrelated_frame_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _rev, state = self._state(root)
            def gate(path, context):
                return "no" if "frame-05" in str(path) else "yes"
            updated, result = rsp.revalidate_state(
                "story-a", state, gate_fn=gate, require_assets=True
            )
            self.assertEqual(updated["frames"]["5"]["status"], "FAIL")
            self.assertEqual(result["status"], "READY_FOR_PUBLISH")
            self.assertEqual(result["usable_frames"], 5)

    def test_revalidation_blocks_two_bad_frames(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _rev, state = self._state(root)
            def gate(path, context):
                return "no" if any(x in str(path) for x in ("frame-04", "frame-05")) else "yes"
            _updated, result = rsp.revalidate_state(
                "story-a", state, gate_fn=gate, require_assets=True
            )
            self.assertEqual(result["status"], "BLOCKED_FRAME_COVERAGE")
            self.assertFalse(result["publishable"])

    def test_revalidation_requires_open_and_close(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _rev, state = self._state(root)
            def gate(path, context):
                return "no" if "frame-01" in str(path) else "yes"
            _updated, result = rsp.revalidate_state(
                "story-a", state, gate_fn=gate, require_assets=True
            )
            self.assertFalse(result["publishable"])
            self.assertFalse(result["opening_ok"])

    def test_context_is_specific_to_each_frame(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _rev, state = self._state(root)
            seen = []
            def gate(path, context):
                seen.append((Path(path).name, context))
                return "yes"
            rsp.revalidate_state("story-a", state, gate_fn=gate, require_assets=True)
            self.assertIn(("frame-03.jpg", "heading 3\ntext 3"), seen)
            self.assertEqual(len(seen), 6)


if __name__ == "__main__":
    unittest.main()
