import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import ready_story_publish as rsp


class StoryReviewGateTests(unittest.TestCase):
    def test_ready_deck_is_deliverable_to_review_without_publication_approval(self):
        allowed = getattr(rsp, "review_delivery_allowed", lambda **_kwargs: False)
        self.assertTrue(allowed(status="READY", approved=False))

    def test_review_deck_is_deliverable_to_review_but_invalid_status_is_not(self):
        allowed = getattr(rsp, "review_delivery_allowed", lambda **_kwargs: False)
        self.assertTrue(allowed(status="REVIEW", approved=False))
        self.assertFalse(allowed(status="BLOCKED", approved=True))

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

    def test_approved_delivery_uses_exact_frozen_files_without_rendering(self):
        deliver = getattr(rsp, "deliver_approved_review", None)
        self.assertIsNotNone(deliver, "deliver_approved_review must exist")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = []
            for index in range(1, 7):
                path = root / f"frame-{index}.png"
                path.write_bytes(f"frame-{index}".encode())
                frames.append(path)
            manifest = rsp.build_review_manifest("Jeddah", "rev123", "READY", frames)
            manifest_path = root / "story-review.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            captured = {}

            def notify(caption, delivered, as_documents=False):
                captured["caption"] = caption
                captured["frames"] = list(delivered)
                captured["as_documents"] = as_documents

            result = deliver(manifest_path, notify_fn=notify)
            self.assertTrue(result)
            self.assertEqual(captured["frames"], frames)
            self.assertTrue(captured["as_documents"])
            self.assertIn("Jeddah", captured["caption"])


if __name__ == "__main__":
    unittest.main()
