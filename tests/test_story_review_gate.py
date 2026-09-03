import hashlib
import tempfile
import unittest
from pathlib import Path

import ready_story_publish as rsp


class StoryReviewGateTests(unittest.TestCase):
    def test_ready_deck_is_not_deliverable_before_human_approval(self):
        allowed = getattr(rsp, "review_delivery_allowed", lambda **_kwargs: True)
        self.assertFalse(allowed(status="READY", approved=False))

    def test_only_ready_approved_deck_is_deliverable(self):
        allowed = getattr(rsp, "review_delivery_allowed", lambda **_kwargs: False)
        self.assertTrue(allowed(status="READY", approved=True))
        self.assertFalse(allowed(status="REVIEW", approved=True))

    def test_review_manifest_freezes_exact_frame_hashes(self):
        build = getattr(rsp, "build_review_manifest", None)
        self.assertIsNotNone(build, "build_review_manifest must exist")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = []
            for index in range(1, 7):
                path = root / f"frame-{index}.png"
                path.write_bytes(f"frame-{index}".encode())
                frames.append(path)
            manifest = build("Jeddah", "rev123", "READY", frames)
            self.assertEqual(manifest["story"], "Jeddah")
            self.assertEqual(manifest["revision"], "rev123")
            self.assertEqual(manifest["status"], "READY")
            self.assertEqual(len(manifest["frames"]), 6)
            self.assertEqual(
                manifest["frames"][0]["sha256"],
                hashlib.sha256(b"frame-1").hexdigest(),
            )

    def test_tampered_frozen_frame_is_rejected(self):
        build = getattr(rsp, "build_review_manifest", None)
        verify = getattr(rsp, "verify_review_manifest", None)
        self.assertIsNotNone(build, "build_review_manifest must exist")
        self.assertIsNotNone(verify, "verify_review_manifest must exist")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = []
            for index in range(1, 7):
                path = root / f"frame-{index}.png"
                path.write_bytes(f"frame-{index}".encode())
                frames.append(path)
            manifest = build("Jeddah", "rev123", "READY", frames)
            frames[3].write_bytes(b"changed after approval")
            with self.assertRaises(ValueError):
                verify(manifest, root)


if __name__ == "__main__":
    unittest.main()
