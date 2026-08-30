import json
import tempfile
import unittest
from pathlib import Path

import guarded_story_publish as gsp
import ready_story_publish as rsp
import runtime_relevance as rr


class PersonalStoryVisualPolicyTests(unittest.TestCase):
    def _ledger(self, verdict):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        path = Path(td.name) / "relevance.json"
        path.write_text(json.dumps({
            "assets": {
                "targeted-sama-1953-10-riyal.jpg": {
                    "stories": {"قصة تأسيس مؤسسة النقد ساما": verdict}
                }
            }
        }), encoding="utf-8")
        return path

    def _selected_local(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        path = Path(td.name) / "story-frame-3.jpg"
        path.write_bytes(b"selected")
        Path(str(path) + ".exempt").write_text(
            "local:targeted-sama-1953-10-riyal.jpg", encoding="utf-8"
        )
        return path

    def test_reviewed_banknote_selected_from_local_library_is_a_valid_visual(self):
        self.assertTrue(rr.trusted_selected_local_visual(
            self._selected_local(),
            "قصة تأسيس مؤسسة النقد ساما",
            self._ledger(rr.STRONG_CONTEXT),
        ))

    def test_wrong_entity_document_is_still_rejected(self):
        self.assertFalse(rr.trusted_selected_local_visual(
            self._selected_local(),
            "قصة تأسيس مؤسسة النقد ساما",
            self._ledger(rr.WRONG_ENTITY),
        ))

    def test_logo_is_optional_for_ready_pool(self):
        ready = rsp.collect_ready_stories(
            ["personal-story"],
            coverage_fn=lambda _story: (list(range(5)), [], "PASS"),
        )
        self.assertEqual(ready, ["personal-story"])

    def test_four_visuals_do_not_enter_ready_pool_even_if_status_is_wrongly_pass(self):
        ready = rsp.collect_ready_stories(
            ["personal-story"],
            coverage_fn=lambda _story: (list(range(4)), [], "PASS"),
        )
        self.assertEqual(ready, [])

    def test_one_text_only_card_can_still_be_ready(self):
        state = {"frames": {
            "1": {"status": "PASS"}, "2": {"status": "PASS"},
            "3": {"status": "PASS"}, "4": {"status": "PASS"},
            "5": {"status": "PASS"}, "6": {"status": "FAIL"},
        }}
        self.assertTrue(gsp.visual_report_is_ready(gsp.visual_accounting(state, 6)))

    def test_two_text_only_cards_are_not_ready(self):
        state = {"frames": {
            "1": {"status": "PASS"}, "2": {"status": "PASS"},
            "3": {"status": "PASS"}, "4": {"status": "PASS"},
            "5": {"status": "FAIL"}, "6": {"status": "FAIL"},
        }}
        self.assertFalse(gsp.visual_report_is_ready(gsp.visual_accounting(state, 6)))

    def test_pre_render_visual_coverage_rejects_two_or_more_empty_slots(self):
        import story_runtime as sr
        self.assertTrue(sr.personal_visual_slots_ready(["1", "2", "3", "4", "5", None]))
        self.assertFalse(sr.personal_visual_slots_ready(["1", "2", "3", "4", None, None]))

    def test_personal_story_does_not_use_logo_as_visual_fallback(self):
        import story_runtime as sr
        self.assertEqual(sr.sb.LOGO_MAX_FRAMES, 0)

    def test_sama_catalog_has_at_least_five_real_visuals(self):
        import story_runtime as sr
        photos, _logos = sr.approved_runtime_visuals("قصة تأسيس مؤسسة النقد ساما")
        names = {Path(p).name for p in photos}
        self.assertGreaterEqual(len(names), 5)
        self.assertIn("first-hajj-receipt.png", names)
        self.assertIn("silver-riyal.png", names)


if __name__ == "__main__":
    unittest.main()
