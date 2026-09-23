import json
import unittest
from pathlib import Path


import model_role_experiment as experiment


class ModelRoleExperimentTests(unittest.TestCase):
    def setUp(self):
        payload = json.loads(Path("evaluation/event_packages.json").read_text(encoding="utf-8"))
        self.case = payload["cases"][0]

    def test_candidates_are_bounded_and_production_baseline_is_included(self):
        self.assertEqual(
            [row["model"] for row in experiment.CANDIDATES],
            ["claude-opus-5", "claude-sonnet-5", "gpt-5.6-sol"],
        )
        self.assertLessEqual(experiment.MAX_EXPERIMENT_COST_USD, 0.75)
        self.assertEqual(experiment.MAX_CASES, 3)

    def test_three_frozen_cases_fit_under_hard_reservation_cap(self):
        payload = json.loads(Path("evaluation/event_packages.json").read_text(encoding="utf-8"))
        reserved = sum(
            experiment.maximum_call_cost(candidate, experiment.prompt_for(case))
            for case in payload["cases"][:experiment.MAX_CASES]
            for candidate in experiment.CANDIDATES
        )
        self.assertLessEqual(reserved, experiment.MAX_EXPERIMENT_COST_USD)

    def test_missing_credentials_make_no_paid_call(self):
        for candidate in experiment.CANDIDATES:
            with self.subTest(candidate=candidate["id"]):
                result = experiment.call_candidate(candidate, "prompt", {})
                self.assertEqual(result, {"status": "missing_credentials"})

    def test_case_input_uses_only_frozen_case_claims(self):
        data = experiment.case_input(self.case)
        ids = {
            fact["id"]
            for source in self.case["sources"]
            for fact in source["facts"]
        }
        self.assertEqual(ids, {row["id"] for row in data["research"]["claims"]})
        self.assertEqual([], data["visual_options"])

    def test_validator_accepts_valid_shape_and_rejects_unknown_claim(self):
        valid = {
            "title": "عنوان",
            "cards": [
                {"kind": "info", "title": "معلومة", "body": "نص", "punch": "خلاصة",
                 "claim_ids": ["apple16-1"], "image_query": "iPhone 16"},
                {"kind": "story", "title": "البداية", "body": "نص", "punch": "تكملة",
                 "claim_ids": ["apple07-1"], "image_query": "first iPhone"},
                {"kind": "story", "title": "النتيجة", "body": "نص", "punch": "نهاية",
                 "claim_ids": ["apple07-2"], "image_query": "first iPhone"},
            ],
        }
        good = experiment.validate_output(json.dumps(valid, ensure_ascii=False), self.case)
        self.assertTrue(good["passed"])
        valid["cards"][2]["claim_ids"] = ["invented"]
        bad = experiment.validate_output(json.dumps(valid, ensure_ascii=False), self.case)
        self.assertEqual({"passed": False, "reason": "claim_ids"}, bad)

    def test_workflow_is_manual_only_and_cannot_publish(self):
        path = Path(".github/workflows/model-role-experiment.yml")
        text = path.read_text(encoding="utf-8")
        self.assertIn("\non:\n  workflow_dispatch:\n", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("POST_TO_SNAPCHAT", text)
        self.assertNotIn("TELEGRAM_TOKEN", text)
        self.assertNotIn("BUNDLE_API_KEY", text)
        self.assertIn("model_role_experiment.py", text)


if __name__ == "__main__":
    unittest.main()
