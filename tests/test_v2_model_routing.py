import unittest
from pathlib import Path


class V2ModelRoutingTests(unittest.TestCase):
    def workflow(self, name):
        return Path(".github/workflows", name).read_text(encoding="utf-8")

    def test_autopilot_keeps_content_roles_on_opus_and_moves_review_roles_to_sonnet(self):
        text = self.workflow("publishing-v2-autopilot.yml")
        self.assertIn("AUTOPILOT_RESEARCHER_MODEL: 'claude-opus-5'", text)
        self.assertIn("AUTOPILOT_WRITER_MODEL: 'claude-opus-5'", text)
        self.assertIn("AUTOPILOT_VISUAL_MODEL: 'claude-sonnet-5'", text)
        self.assertIn("AUTOPILOT_REVIEWER_MODEL: 'claude-sonnet-5'", text)

    def test_saved_replay_reuses_opus_writer_but_sonnet_reviewer(self):
        text = self.workflow("publishing-v2-saved-replay.yml")
        self.assertIn("AUTOPILOT_WRITER_MODEL: 'claude-opus-5'", text)
        self.assertIn("AUTOPILOT_REVIEWER_MODEL: 'claude-sonnet-5'", text)

    def test_candidate_probe_matches_production_routing(self):
        text = self.workflow("publishing-v2-candidate-probe.yml")
        self.assertIn("AUTOPILOT_RESEARCHER_MODEL: claude-opus-5", text)
        self.assertIn("AUTOPILOT_WRITER_MODEL: claude-opus-5", text)
        self.assertIn("AUTOPILOT_VISUAL_MODEL: claude-sonnet-5", text)
        self.assertIn("AUTOPILOT_REVIEWER_MODEL: claude-sonnet-5", text)


if __name__ == "__main__":
    unittest.main()
