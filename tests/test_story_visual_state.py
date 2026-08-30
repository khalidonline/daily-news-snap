import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PIL import Image

import story_visual_state as svs


class StoryVisualStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("STORY_VISUAL_STATE_ROOT")
        self.old_mode = os.environ.get("STORY_OPERATION_MODE")
        self.old_repair_frames = os.environ.get("STORY_REPAIR_FRAMES")
        os.environ["STORY_VISUAL_STATE_ROOT"] = self.tmp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("STORY_VISUAL_STATE_ROOT", None)
        else:
            os.environ["STORY_VISUAL_STATE_ROOT"] = self.old
        if self.old_mode is None:
            os.environ.pop("STORY_OPERATION_MODE", None)
        else:
            os.environ["STORY_OPERATION_MODE"] = self.old_mode
        if self.old_repair_frames is None:
            os.environ.pop("STORY_REPAIR_FRAMES", None)
        else:
            os.environ["STORY_REPAIR_FRAMES"] = self.old_repair_frames
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

    def test_visual_only_human_repair_reopens_pass_slot_and_rejects_prior_asset(self):
        root = Path(self.tmp.name)
        asset1 = root / "asset1.jpg"
        asset2 = root / "asset2.jpg"
        Image.new("RGB", (12, 12), (11, 11, 11)).save(asset1)
        Image.new("RGB", (12, 12), (22, 22, 22)).save(asset2)
        previous = {"frames": {
            "1": {
                "status": "PASS",
                "image_source": str(asset1),
                "frame_payload": {"heading": "old 1", "text": "old 1"},
            },
            "2": {
                "status": "PASS",
                "image_source": str(asset2),
                "frame_payload": {"heading": "old 2", "text": "old 2"},
            },
        }}
        svs.save_visual_state("story", "rev", previous)

        calls = []
        out_dir = root / "out"
        out_dir.mkdir()
        sb = SimpleNamespace(OUT_DIR=out_dir)
        sb._photo_digest = lambda path: Path(path).read_bytes()
        sb.same_picture = lambda left, right: left == right

        def find_photo(spec, out_path, seen=(), context="", allow_neutral=True, bank=None):
            frame_no = svs._frame_no_from_path(out_path)
            calls.append((frame_no, tuple(seen)))
            Image.new("RGB", (12, 12), (99, frame_no or 0, 1)).save(out_path)
            return str(out_path)

        sb.find_photo = find_photo

        def find_all_photos(brief):
            photos, seen = [], []
            for frame_no, frame in enumerate(brief["frames"], start=1):
                slot = sb.OUT_DIR / f"story-frame-{frame_no}.jpg"
                photo = sb.find_photo(frame, slot, seen, "")
                photos.append(photo)
                if photo:
                    seen.append(sb._photo_digest(photo))
            return photos

        sb.find_all_photos = find_all_photos
        svs.configure(sb)
        os.environ["STORY_OPERATION_MODE"] = "visual_only"
        os.environ["STORY_REPAIR_FRAMES"] = "2"

        with mock.patch.object(svs, "_effective_revision", return_value="rev"):
            photos = sb.find_all_photos({
                "story": "story",
                "frames": [
                    {"heading": "incoming 1", "text": "incoming 1"},
                    {"heading": "incoming 2", "text": "incoming 2"},
                ],
            })

        self.assertEqual([2], [frame_no for frame_no, _seen in calls])
        self.assertIn(sb._photo_digest(asset2), calls[0][1])
        self.assertEqual(sb._photo_digest(asset1), sb._photo_digest(photos[0]))
        self.assertNotEqual(sb._photo_digest(asset2), sb._photo_digest(photos[1]))


if __name__ == "__main__":
    unittest.main()
