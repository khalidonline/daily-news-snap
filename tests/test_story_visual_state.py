import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import story_visual_state as svs


class StoryVisualStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("STORY_VISUAL_STATE_ROOT")
        os.environ["STORY_VISUAL_STATE_ROOT"] = self.tmp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("STORY_VISUAL_STATE_ROOT", None)
        else:
            os.environ["STORY_VISUAL_STATE_ROOT"] = self.old
        self.tmp.cleanup()

    def test_failed_frame_indices_returns_only_non_pass_slots(self):
        state = {"frames": {
            "1": {"status": "PASS", "image_source": "a.jpg"},
            "2": {"status": "FAIL", "image_source": None},
            "3": {"status": "PASS", "image_source": "c.jpg"},
        }}
        self.assertEqual((2,), svs.failed_frame_indices(state))

    def test_state_round_trip_is_atomic_and_revision_scoped(self):
        state = {"status": "VISUAL_ASSEMBLY", "frames": {"1": {"status": "FAIL"}}}
        path = svs.save_visual_state("قصة اختبار", "rev-a", state)
        self.assertTrue(path.exists())
        self.assertEqual(state, svs.load_visual_state("قصة اختبار", "rev-a"))
        self.assertEqual({}, svs.load_visual_state("قصة اختبار", "rev-b"))

    def test_preserve_approved_frames_keeps_text_and_image(self):
        previous = {"frames": {
            "1": {"status": "PASS", "heading": "قديم 1", "text": "نص 1", "image_source": "a.jpg"},
            "2": {"status": "FAIL", "heading": "قديم 2", "text": "نص 2", "image_source": None},
            "3": {"status": "PASS", "heading": "قديم 3", "text": "نص 3", "image_source": "c.jpg"},
        }}
        incoming = [
            {"heading": "جديد 1", "text": "تغيير غير مسموح"},
            {"heading": "جديد 2", "text": "إصلاح"},
            {"heading": "جديد 3", "text": "تغيير غير مسموح"},
        ]
        kept = svs.preserve_approved_frames(previous, incoming, (2,))
        self.assertEqual("قديم 1", kept[0]["heading"])
        self.assertEqual("جديد 2", kept[1]["heading"])
        self.assertEqual("قديم 3", kept[2]["heading"])

    def test_capture_visuals_persists_reusable_assets(self):
        source = Path(self.tmp.name) / "picked.jpg"
        Image.new("RGB", (20, 20)).save(source)
        brief = {"frames": [{"heading": "h", "text": "t", "punch": ""}]}
        state = svs.capture_visual_state("story", "rev", brief, [str(source)])
        row = state["frames"]["1"]
        self.assertEqual("PASS", row["status"])
        self.assertTrue(Path(row["image_source"]).exists())
        self.assertTrue(row["asset_hash"])

    def test_visual_only_reuses_pass_assets_and_searches_only_failed_slots(self):
        asset1 = Path(self.tmp.name) / "asset1.jpg"
        asset3 = Path(self.tmp.name) / "asset3.jpg"
        Image.new("RGB", (10, 10), (1, 1, 1)).save(asset1)
        Image.new("RGB", (10, 10), (3, 3, 3)).save(asset3)
        previous = {"frames": {
            "1": {"status": "PASS", "image_source": str(asset1)},
            "2": {"status": "FAIL", "image_source": None},
            "3": {"status": "PASS", "image_source": str(asset3)},
        }}
        searched = []

        def search(frame_no, out_path):
            searched.append(frame_no)
            Image.new("RGB", (10, 10), (2, 2, 2)).save(out_path)
            return str(out_path)

        outputs = svs.repair_visual_slots(
            previous,
            [Path(self.tmp.name) / f"out-{i}.jpg" for i in (1, 2, 3)],
            search,
        )
        self.assertEqual([2], searched)
        self.assertEqual(3, len(outputs))
        self.assertTrue(all(Path(p).exists() for p in outputs))


if __name__ == "__main__":
    unittest.main()
