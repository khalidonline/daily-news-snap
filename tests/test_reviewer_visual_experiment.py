import unittest
from pathlib import Path

import reviewer_visual_experiment as experiment


class ReviewerVisualExperimentTests(unittest.TestCase):
    def test_models_and_shared_cap_are_bounded(self):
        self.assertEqual(experiment.MODELS, ("claude-opus-5", "claude-sonnet-5"))
        self.assertLessEqual(experiment.SHARED_RESERVATION_MICRO_USD, 1_500_000)

    def test_local_ledger_releases_unused_reservation_after_settlement(self):
        ledger = experiment.LocalLedger(1_000_000)
        first = ledger.reserve(700_000, "a")
        ledger.settle(first, 200_000)
        second = ledger.reserve(700_000, "b")
        ledger.settle(second, 100_000)
        self.assertEqual(ledger.charged_micro_usd, 300_000)

    def test_local_ledger_blocks_worst_case_that_cannot_fit(self):
        ledger = experiment.LocalLedger(1_000_000)
        first = ledger.reserve(700_000, "a")
        ledger.settle(first, 500_000)
        with self.assertRaises(Exception):
            ledger.reserve(600_000, "b")

    def test_reviewer_overall_requires_every_check_and_card(self):
        decision = {
            "checks": {key: True for key in experiment.REVIEW_CHECKS},
            "card_checks": [{"readable": True, "relevant": True}],
        }
        self.assertTrue(experiment.reviewer_overall(decision))
        decision["checks"]["factual"] = False
        self.assertFalse(experiment.reviewer_overall(decision))

    def test_visual_case_hides_selected_image_from_cards_and_adds_distractor(self):
        state = {
            "package": {
                "cards": [
                    {"kind": "info", "title": "A", "body": "B", "punch": "C",
                     "image_query": "subject", "image": {"asset_id": "one", "title": "One"}},
                    {"kind": "story", "title": "D", "body": "E", "punch": "F",
                     "image_query": "subject", "image": {"asset_id": "two", "title": "Two"}},
                ]
            }
        }
        distractor = {
            "package": {
                "cards": [
                    {"kind": "info", "title": "X", "body": "Y", "punch": "Z",
                     "image_query": "other", "image": {"asset_id": "wrong", "title": "Wrong"}}
                ]
            }
        }
        case = experiment.visual_case(state, distractor, "case")
        self.assertEqual(case["expected_ids"], ["one", "two"])
        self.assertEqual(case["distractor_ids"], ["wrong"])
        self.assertNotIn("image", case["input"]["cards"][0])

    def test_workflow_is_manual_only_and_has_no_publish_credentials(self):
        text = Path(".github/workflows/reviewer-visual-experiment.yml").read_text(encoding="utf-8")
        self.assertIn("\non:\n  workflow_dispatch:\n", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("POST_TO_SNAPCHAT", text)
        self.assertNotIn("TELEGRAM_TOKEN", text)
        self.assertNotIn("BUNDLE_API_KEY", text)
        self.assertIn("35849539333", text)
        self.assertIn("35916577071", text)


if __name__ == "__main__":
    unittest.main()
