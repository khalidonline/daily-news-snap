import unittest

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


if __name__ == "__main__":
    unittest.main()
