import json
import tempfile
import unittest
from pathlib import Path

import publish_cards as pc


class PublishCardsSelectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cards = Path(self.tmp.name)
        self.old_cards_dir = pc.CARDS_DIR
        pc.CARDS_DIR = str(self.cards)

    def tearDown(self):
        pc.CARDS_DIR = self.old_cards_dir
        self.tmp.cleanup()

    def _sidecar(self, stamp, *, story, title):
        payload = {
            "story": story,
            "title": title,
            "caption": f"caption for {story}",
            "frames": [],
        }
        (self.cards / f"{stamp}-story.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def test_unique_partial_story_name_resolves_to_stamp(self):
        self._sidecar(
            "2026-08-25-11am",
            story="سليمان الراجحي: من الصرافة إلى أكبر مصرف إسلامي",
            title="قصة سليمان الراجحي",
        )
        self._sidecar(
            "2026-08-26-2pm",
            story="Jack Bogle: أنشأ صندوق المؤشرات ورفض أن يصبح ملياردير",
            title="الصندوق الذي سمّوه حماقة بوغل",
        )

        self.assertTrue(
            hasattr(pc, "resolve_story_selector"),
            "publish_cards needs story-name selector support",
        )
        self.assertEqual(
            pc.resolve_story_selector("سليمان"),
            "2026-08-25-11am",
        )

    def test_ambiguous_partial_story_name_refuses(self):
        self._sidecar(
            "2026-08-25-11am",
            story="سليمان الراجحي: من الصرافة إلى أكبر مصرف إسلامي",
            title="قصة سليمان الراجحي",
        )
        self._sidecar(
            "2026-08-25-12pm",
            story="مصرف الراجحي: كيف بدأ من محل صرافة",
            title="قصة مصرف الراجحي",
        )

        with self.assertRaises(SystemExit) as ctx:
            pc.resolve_story_selector("الراجحي")
        self.assertIn("multiple", str(ctx.exception).lower())
        self.assertIn("2026-08-25-11am", str(ctx.exception))
        self.assertIn("2026-08-25-12pm", str(ctx.exception))

    def test_exact_stamp_is_preserved(self):
        self.assertEqual(
            pc.resolve_story_selector("2026-08-26-2pm"),
            "2026-08-26-2pm",
        )


if __name__ == "__main__":
    unittest.main()
