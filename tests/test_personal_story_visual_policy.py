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

    def test_logo_is_optional_for_render_pool(self):
        ready = rsp.collect_ready_stories(
            ["personal-story"],
            coverage_fn=lambda _story: (list(range(4)), [], "PASS"),
        )
        self.assertEqual(ready, ["personal-story"])

    def test_three_visuals_do_not_enter_render_pool(self):
        ready = rsp.collect_ready_stories(
            ["personal-story"],
            coverage_fn=lambda _story: (list(range(3)), [], "PASS"),
        )
        self.assertEqual(ready, [])

    def test_all_six_visual_frames_are_ready_and_not_capped(self):
        state = {"frames": {str(i): {"status": "PASS"} for i in range(1, 7)}}
        report = gsp.visual_accounting(state, 6)
        self.assertEqual(report["approved_visual_count"], 6)
        self.assertTrue(gsp.visual_report_is_ready(report))

    def test_middle_text_only_card_can_still_be_ready(self):
        state = {"frames": {
            "1": {"status": "PASS"}, "2": {"status": "PASS"},
            "3": {"status": "FAIL"}, "4": {"status": "PASS"},
            "5": {"status": "PASS"}, "6": {"status": "PASS"},
        }}
        self.assertTrue(gsp.visual_report_is_ready(gsp.visual_accounting(state, 6)))

    def test_frame_one_must_have_a_meaningful_visual(self):
        state = {"frames": {
            "1": {"status": "FAIL"}, "2": {"status": "PASS"},
            "3": {"status": "PASS"}, "4": {"status": "PASS"},
            "5": {"status": "PASS"}, "6": {"status": "PASS"},
        }}
        self.assertFalse(gsp.visual_report_is_ready(gsp.visual_accounting(state, 6)))

    def test_frame_six_must_have_a_meaningful_visual(self):
        state = {"frames": {
            "1": {"status": "PASS"}, "2": {"status": "PASS"},
            "3": {"status": "PASS"}, "4": {"status": "PASS"},
            "5": {"status": "PASS"}, "6": {"status": "FAIL"},
        }}
        self.assertFalse(gsp.visual_report_is_ready(gsp.visual_accounting(state, 6)))

    def test_two_text_only_cards_are_not_ready(self):
        state = {"frames": {
            "1": {"status": "PASS"}, "2": {"status": "PASS"},
            "3": {"status": "PASS"}, "4": {"status": "FAIL"},
            "5": {"status": "FAIL"}, "6": {"status": "PASS"},
        }}
        self.assertFalse(gsp.visual_report_is_ready(gsp.visual_accounting(state, 6)))

    def test_pre_render_visual_gate_requires_open_and_close_when_slots_are_known(self):
        import story_runtime as sr
        self.assertTrue(sr.personal_visual_slots_ready(["1", "2", "3", "4", "5", "6"]))
        self.assertTrue(sr.personal_visual_slots_ready(["1", "2", None, "4", "5", "6"]))
        self.assertFalse(sr.personal_visual_slots_ready([None, "2", "3", "4", "5", "6"]))
        self.assertFalse(sr.personal_visual_slots_ready(["1", "2", "3", "4", "5", None]))
        self.assertFalse(sr.personal_visual_slots_ready(["1", "2", None, "4", None, "6"]))

    def test_personal_story_does_not_use_logo_as_visual_fallback(self):
        import story_runtime as sr
        self.assertEqual(sr.sb.LOGO_MAX_FRAMES, 0)

    def test_story_runtime_hard_disables_generated_story_frames(self):
        import story_runtime as sr
        self.assertFalse(sr.sb.ALLOW_STORY_GENERATION)

    def test_story_runtime_prompt_requests_diverse_real_visuals(self):
        import story_runtime as sr
        prompt = " ".join(sr.sb.SYSTEM_PROMPT.split())
        for term in ("المنتجات", "الموظفين", "العمليات", "الفروع", "التغليف"):
            self.assertIn(term, prompt)
        self.assertIn("صور حقيقية", prompt)
        self.assertIn("لا تستخدم صوراً مولدة", prompt)

    def test_quarantined_upside_down_mcdonalds_visual_is_not_countable(self):
        self.assertFalse(rr.asset_countable(
            "mcdonalds-jubail.jpg",
            "قصة ماكدونالدز في السعودية وعائلات الامتياز",
        ))

    def test_explicit_strong_context_can_match_without_literal_story_tags(self):
        import story_runtime as sr
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        ledger = Path(td.name) / "relevance.json"
        ledger.write_text(json.dumps({
            "assets": {
                "brand-meal.jpg": {
                    "stories": {"قصة العلامة": rr.STRONG_CONTEXT},
                    "source_url": "https://example.com/real-brand-meal.jpg",
                }
            }
        }), encoding="utf-8")
        entry = {"path": Path("images/brand-meal.jpg"), "tags": ["meal", "employee", "restaurant"]}
        self.assertTrue(sr._matches_story(entry, "قصة العلامة", ledger_path=ledger))

    def test_scoped_runtime_inventory_does_not_hide_contextual_assets(self):
        import story_runtime as sr
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        index = Path(td.name) / "approved.txt"
        index.write_text(
            "brand-meal.jpg | meal, employee, kitchen | Official brand source\n",
            encoding="utf-8",
        )
        old_index = sr.nb.IMAGES_INDEX
        old_story = getattr(sr.sb, "_ACTIVE_EDITORIAL_STORY", "")
        try:
            sr.nb.IMAGES_INDEX = index
            sr.sb._ACTIVE_EDITORIAL_STORY = "قصة العلامة"
            prompt = sr._editorial_prompt_for_revision()
        finally:
            sr.nb.IMAGES_INDEX = old_index
            sr.sb._ACTIVE_EDITORIAL_STORY = old_story
        self.assertIn("brand-meal.jpg", prompt)
        self.assertIn("meal", prompt)

    def test_sama_catalog_has_at_least_five_real_visuals(self):
        import story_runtime as sr
        photos, _logos = sr.approved_runtime_visuals("قصة تأسيس مؤسسة النقد ساما")
        names = {Path(p).name for p in photos}
        self.assertGreaterEqual(len(names), 5)
        self.assertIn("first-hajj-receipt.png", names)
        self.assertIn("silver-riyal.png", names)


if __name__ == "__main__":
    unittest.main()
