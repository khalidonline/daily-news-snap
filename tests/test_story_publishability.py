import unittest
from unittest.mock import patch

import story_publishability as sp


class StoryPublishabilityTests(unittest.TestCase):
    def _state(self, failed=(), *, story="story-a", policy=None):
        frames = {}
        for i in range(1, 7):
            frames[str(i)] = {
                "status": "FAIL" if i in set(failed) else "PASS",
                "image_source": f"state/story_visuals/x/assets/frame-{i:02d}.jpg",
            }
        payload = {"story": story, "frames": frames}
        if policy is not None:
            payload["publishability_policy"] = policy
        return payload

    def _evaluate(self, state, story="story-a"):
        return sp.publishability_from_visual_state(story, state)

    def test_six_frame_current_policy_state_is_publishable(self):
        result = self._evaluate(self._state(policy=sp.PUBLISHABILITY_POLICY))
        self.assertEqual(result["status"], "READY_FOR_PUBLISH")
        self.assertTrue(result["publishable"])

    def test_one_middle_text_only_frame_is_publishable(self):
        result = self._evaluate(self._state(failed=(3,), policy=sp.PUBLISHABILITY_POLICY))
        self.assertEqual(result["status"], "READY_FOR_PUBLISH")
        self.assertEqual(result["usable_frames"], 5)

    def test_opening_frame_failure_blocks_story(self):
        result = self._evaluate(self._state(failed=(1,), policy=sp.PUBLISHABILITY_POLICY))
        self.assertEqual(result["status"], "BLOCKED_FRAME_COVERAGE")
        self.assertFalse(result["publishable"])

    def test_closing_frame_failure_blocks_story(self):
        result = self._evaluate(self._state(failed=(6,), policy=sp.PUBLISHABILITY_POLICY))
        self.assertEqual(result["status"], "BLOCKED_FRAME_COVERAGE")
        self.assertFalse(result["publishable"])

    def test_two_missing_middle_frames_block_story(self):
        result = self._evaluate(self._state(failed=(3, 4), policy=sp.PUBLISHABILITY_POLICY))
        self.assertEqual(result["status"], "BLOCKED_FRAME_COVERAGE")
        self.assertFalse(result["publishable"])

    def test_old_pre_frame_relevance_state_fails_closed(self):
        result = self._evaluate(self._state(policy=None))
        self.assertEqual(result["status"], "BLOCKED_STALE_EVIDENCE")
        self.assertFalse(result["publishable"])

    def test_story_mismatch_fails_closed(self):
        result = self._evaluate(
            self._state(story="different-story", policy=sp.PUBLISHABILITY_POLICY)
        )
        self.assertEqual(result["status"], "BLOCKED_STALE_EVIDENCE")
        self.assertFalse(result["publishable"])

    def test_missing_state_fails_closed(self):
        result = self._evaluate({})
        self.assertEqual(result["status"], "BLOCKED_NO_FRAME_EVIDENCE")
        self.assertFalse(result["publishable"])

    def test_auto_selector_never_falls_back_to_inventory_count(self):
        import guarded_story_publish as gsp
        blocked = {
            "status": "BLOCKED_STALE_EVIDENCE",
            "publishable": False,
            "usable_frames": 6,
            "opening_ok": True,
            "closing_ok": True,
        }
        with patch.object(gsp.sp, "evaluate_story", return_value=blocked), \
             patch.object(gsp.rsp.sr, "coverage", side_effect=AssertionError("inventory used")):
            self.assertFalse(gsp._auto_story_has_visual_buffer("railway-story"))

    def test_global_ready_pool_uses_publishability_for_every_story(self):
        import guarded_story_publish as gsp
        verdicts = {
            "ready": {
                "status": "READY_FOR_PUBLISH", "publishable": True,
                "usable_frames": 6, "opening_ok": True, "closing_ok": True,
            },
            "railway": {
                "status": "BLOCKED_FRAME_COVERAGE", "publishable": False,
                "usable_frames": 3, "opening_ok": False, "closing_ok": False,
            },
            "sabic": {
                "status": "BLOCKED_STALE_EVIDENCE", "publishable": False,
                "usable_frames": 6, "opening_ok": True, "closing_ok": True,
            },
        }
        with patch.object(gsp.sp, "evaluate_story", side_effect=lambda story: verdicts[story]):
            self.assertEqual(
                gsp._personal_collect_ready_stories(["ready", "railway", "sabic"]),
                ["ready"],
            )

    def test_empty_ready_pool_bootstraps_a_renderable_story(self):
        import guarded_story_publish as gsp
        coverage = {
            "weak": (["1", "2", "3"], ["logo"], "FAIL"),
            "ready": (["1", "2", "3", "4"], ["logo"], "PASS"),
        }
        with patch.object(gsp.rsp.sr, "choose_runtime_story", return_value=""), \
             patch.object(gsp.rsp.sb, "load_stories", return_value=["weak", "ready"]), \
             patch.object(gsp.rsp.sr, "coverage", side_effect=lambda story: coverage[story]):
            self.assertEqual(gsp._personal_resolve_story(), "ready")


if __name__ == "__main__":
    unittest.main()
