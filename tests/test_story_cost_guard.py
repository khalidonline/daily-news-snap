import json
import os
import tempfile
import unittest
from pathlib import Path

import story_cost_guard as scg


class CostGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = {key: os.environ.get(key) for key in (
            "STORY_COST_STATE_ROOT", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
            "STORY_REGENERATION_NONCE", "STORY_MODEL_INPUT_USD_PER_M",
            "STORY_MODEL_OUTPUT_USD_PER_M",
        )}
        os.environ["STORY_COST_STATE_ROOT"] = self.tmp.name
        for key in self.saved:
            if key != "STORY_COST_STATE_ROOT":
                os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def test_visual_only_forbids_paid_call(self):
        with self.assertRaises(scg.EditorialSpendBlocked):
            scg.reserve_editorial_call("story", "rev", "visual_only")

    def test_second_call_for_same_revision_is_blocked(self):
        first = scg.reserve_editorial_call("story", "rev", "auto")
        scg.record_model_result(
            first, model="claude-opus-5", message_id="msg_1",
            input_tokens=100, output_tokens=50, status="success",
        )
        with self.assertRaises(scg.EditorialSpendBlocked):
            scg.reserve_editorial_call("story", "rev", "auto")

    def test_missing_price_configuration_does_not_disable_call_guard(self):
        scg.reserve_editorial_call("story", "rev", "auto")
        with self.assertRaises(scg.EditorialSpendBlocked):
            scg.reserve_editorial_call("story", "rev", "auto")

    def test_ledger_includes_github_run_identity_and_usage(self):
        os.environ["GITHUB_RUN_ID"] = "12345"
        os.environ["GITHUB_RUN_ATTEMPT"] = "2"
        reservation = scg.reserve_editorial_call("story", "rev", "auto")
        scg.record_model_result(
            reservation, model="claude-opus-5", message_id="msg_abc",
            input_tokens=1200, output_tokens=300, status="success",
        )
        row = json.loads(scg.usage_ledger_path().read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual("12345", row["run_id"])
        self.assertEqual("2", row["run_attempt"])
        self.assertEqual("msg_abc", row["message_id"])
        self.assertEqual(1200, row["input_tokens"])
        self.assertEqual(300, row["output_tokens"])
        self.assertIsNone(row["estimated_usd"])

    def test_configured_price_is_estimated_but_not_required(self):
        os.environ["STORY_MODEL_INPUT_USD_PER_M"] = "10"
        os.environ["STORY_MODEL_OUTPUT_USD_PER_M"] = "20"
        reservation = scg.reserve_editorial_call("story", "rev", "auto")
        scg.record_model_result(
            reservation, model="model", message_id="msg",
            input_tokens=1_000_000, output_tokens=500_000, status="success",
        )
        row = json.loads(scg.usage_ledger_path().read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(20.0, row["estimated_usd"])

    def test_regeneration_requires_explicit_nonce_and_is_separately_auditable(self):
        with self.assertRaises(scg.EditorialSpendBlocked):
            scg.reserve_editorial_call("story", "rev", "regenerate_editorial")
        os.environ["STORY_REGENERATION_NONCE"] = "run-99"
        reservation = scg.reserve_editorial_call("story", "rev", "regenerate_editorial")
        self.assertNotEqual("rev", reservation.guard_revision)
        self.assertEqual("rev", reservation.revision)

    def test_cache_hit_is_audited_without_reserving_paid_call(self):
        scg.record_cache_hit("story", "rev", run_id="9", run_attempt="3")
        row = json.loads(scg.usage_ledger_path().read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual("cache_hit", row["event"])
        self.assertTrue(row["cache_hit"])
        self.assertEqual("9", row["run_id"])
        self.assertEqual("3", row["run_attempt"])


if __name__ == "__main__":
    unittest.main()
