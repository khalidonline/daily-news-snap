import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ModelUsagePricingTests(unittest.TestCase):
    def test_anthropic_cost_includes_tokens_cache_and_web_search(self):
        import model_usage

        usage = {
            "input_tokens": 1_000_000,
            "output_tokens": 100_000,
            "cache_creation_input_tokens": 100_000,
            "cache_read_input_tokens": 500_000,
            "server_tool_use": {"web_search_requests": 3},
        }

        self.assertEqual(
            model_usage.estimate_anthropic_cost("claude-sonnet-5", usage),
            3.38,
        )

    def test_unknown_model_is_recorded_without_inventing_a_price(self):
        import model_usage

        self.assertIsNone(
            model_usage.estimate_anthropic_cost(
                "future-model", {"input_tokens": 10, "output_tokens": 5}
            )
        )


class ModelUsageLedgerTests(unittest.TestCase):
    def setUp(self):
        import model_usage

        model_usage.reset_run_state()

    def tearDown(self):
        import model_usage

        model_usage.reset_run_state()

    def test_response_is_persisted_with_run_and_cost_dimensions(self):
        import model_usage

        response = {
            "id": "msg_123",
            "usage": {
                "input_tokens": 1_000,
                "output_tokens": 200,
                "server_tool_use": {"web_search_requests": 2},
            },
        }
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {"GITHUB_RUN_ID": "9001", "GITHUB_RUN_ATTEMPT": "2"},
            clear=False,
        ):
            path = Path(td) / "usage.jsonl"
            row = model_usage.record_anthropic_response(
                bot="news",
                purpose="editorial",
                model="claude-sonnet-5",
                response=response,
                path=path,
            )
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(saved, row)
        self.assertEqual(saved["provider"], "anthropic")
        self.assertEqual(saved["bot"], "news")
        self.assertEqual(saved["purpose"], "editorial")
        self.assertEqual(saved["run_id"], "9001")
        self.assertEqual(saved["run_attempt"], "2")
        self.assertEqual(saved["message_id"], "msg_123")
        self.assertEqual(saved["web_search_requests"], 2)
        self.assertEqual(saved["estimated_usd"], 0.024)

    def test_unknown_external_call_keeps_visibility_without_fake_cost(self):
        import model_usage

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "usage.jsonl"
            row = model_usage.record_external_call(
                provider="byteplus",
                bot="topic",
                purpose="image_generation",
                model="seedream",
                path=path,
            )

        self.assertEqual(row["provider"], "byteplus")
        self.assertIsNone(row["estimated_usd"])


class PaidResponseCeilingTests(unittest.TestCase):
    def setUp(self):
        import model_usage

        model_usage.reset_run_state()

    def tearDown(self):
        import model_usage

        model_usage.reset_run_state()

    def test_next_paid_response_is_blocked_after_bucket_limit(self):
        import model_usage

        model_usage.require_response_capacity("topic_research", 1)
        model_usage.note_successful_response("topic_research")

        with self.assertRaisesRegex(model_usage.ModelBudgetExceeded, "topic_research"):
            model_usage.require_response_capacity("topic_research", 1)

    def test_transport_failure_does_not_consume_paid_response_capacity(self):
        import model_usage

        model_usage.require_response_capacity("breaking_classifier", 1)
        model_usage.require_response_capacity("breaking_classifier", 1)

    def test_next_call_is_blocked_after_run_cost_ceiling(self):
        import model_usage

        with tempfile.TemporaryDirectory() as td:
            model_usage.record_anthropic_response(
                bot="news",
                purpose="editorial",
                model="claude-sonnet-5",
                response={
                    "usage": {"input_tokens": 10_000, "output_tokens": 1_000}
                },
                path=Path(td) / "usage.jsonl",
            )

        with self.assertRaisesRegex(model_usage.ModelBudgetExceeded, "run cost"):
            model_usage.require_run_cost_capacity(0.02)

    def test_github_run_cost_is_recovered_across_processes(self):
        import model_usage

        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {
                "GITHUB_RUN_ID": "same-workflow-run",
                "MODEL_USAGE_PATH": str(Path(td) / "usage.jsonl"),
            },
            clear=False,
        ):
            model_usage.record_anthropic_response(
                bot="breaking",
                purpose="classifier",
                model="claude-haiku-4-5-20251001",
                response={
                    "usage": {"input_tokens": 20_000, "output_tokens": 2_000}
                },
            )
            # A subprocess starts with empty in-memory counters, but must still
            # honor usage already written by the parent workflow process.
            model_usage.reset_run_state()
            with self.assertRaisesRegex(
                model_usage.ModelBudgetExceeded, "run cost"
            ):
                model_usage.require_run_cost_capacity(0.02)


class UsageSummaryTests(unittest.TestCase):
    def test_summary_groups_cost_by_bot_and_flags_unpriced_calls(self):
        import model_usage

        rows = [
            {"bot": "news", "estimated_usd": 0.1},
            {"bot": "news", "estimated_usd": 0.2},
            {"bot": "topic", "estimated_usd": None},
        ]

        self.assertEqual(
            model_usage.summarize_rows(rows),
            {
                "calls": 3,
                "estimated_usd": 0.3,
                "unpriced_calls": 1,
                "by_bot": {
                    "news": {"calls": 2, "estimated_usd": 0.3, "unpriced_calls": 0},
                    "topic": {"calls": 1, "estimated_usd": 0.0, "unpriced_calls": 1},
                },
                "by_route": {
                    "news/unknown": {
                        "calls": 2,
                        "estimated_usd": 0.3,
                        "unpriced_calls": 0,
                    },
                    "topic/unknown": {
                        "calls": 1,
                        "estimated_usd": 0.0,
                        "unpriced_calls": 1,
                    },
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
