"""Offline behavioral coverage; the all-cases-fit preflight remains separate."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import model_role_experiment as experiment


class ModelExperimentCapTests(unittest.TestCase):
    def run_offline(self):
        requests = []

        def response(url, headers, payload):
            requests.append(payload["model"])
            usage = {"input_tokens": 1, "output_tokens": 1}
            if url == "https://api.anthropic.com/v1/messages":
                return {"id": "offline", "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": "{}"}],
                        "usage": usage}
            if url == "https://api.openai.com/v1/responses":
                return {"id": "offline", "status": "completed",
                        "output": [{"type": "message", "content": [
                            {"type": "output_text", "text": "{}"}]}],
                        "usage": usage}
            raise AssertionError("unexpected provider")

        # Explicit fake keys exercise adapters; no inherited environment or
        # GitHub credentials. Only the HTTP boundary is replaced, not the cap,
        # candidate loop, response parsing, pricing or artifact writing.
        env = {"ANTHROPIC_API_KEY": "offline-test", "OPENAI_API_KEY": "offline-test"}
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(experiment, "_request", side_effect=response):
            output = Path(tmp)
            result = experiment.run(Path("evaluation/event_packages.json"), output, env)
            saved = json.loads((output / "model-experiment-key.json").read_text())
            summary = json.loads((output / "summary.json").read_text())
        self.assertEqual(saved, result)
        self.assertFalse(result["published"])
        self.assertFalse(result["production_changed"])
        self.assertEqual(summary["failed_calls"], 0)
        self.assertEqual(summary["completed_calls"], len(requests))
        self.assertLessEqual(result["reserved_maximum_usd"], 0.75)
        return result, requests

    def test_frozen_cases_skip_last_request_before_transport(self):
        # Stress the unchanged cap with a hypothetical oversized two-case batch.
        with patch.object(experiment, "MAX_CASES", 2):
            result, requests = self.run_offline()
        self.assertEqual(requests, ["claude-opus-5", "claude-sonnet-5", "gpt-5.6-sol",
                                    "claude-opus-5", "claude-sonnet-5"])
        self.assertEqual(result["cases"][1]["outputs"][2],
                         {"label": "C", "status": "cost_cap_reached"})
        self.assertAlmostEqual(result["reserved_maximum_usd"], 0.733462)

    def test_exact_cap_allows_last_request(self):
        # Six requests at $0.125 exactly fill the existing $0.75 cap.
        with patch.object(experiment, "MAX_CASES", 2), patch.object(experiment, "maximum_call_cost", return_value=0.125):
            result, requests = self.run_offline()
        self.assertEqual(len(requests), 6)
        self.assertEqual(result["reserved_maximum_usd"], 0.75)
        self.assertTrue(all(o["status"] == "completed"
                            for c in result["cases"] for o in c["outputs"]))

    def test_over_cap_skips_last_request(self):
        with patch.object(experiment, "MAX_CASES", 2), patch.object(experiment, "maximum_call_cost", return_value=0.125001):
            result, requests = self.run_offline()
        self.assertEqual(len(requests), 5)
        self.assertEqual(result["cases"][1]["outputs"][2],
                         {"label": "C", "status": "cost_cap_reached"})
        self.assertAlmostEqual(result["reserved_maximum_usd"], 0.625005)

    def test_default_batch_compares_all_models_on_one_case(self):
        result, requests = self.run_offline()
        self.assertEqual(len(result['cases']), 1)
        self.assertEqual(requests, ['claude-opus-5', 'claude-sonnet-5', 'gpt-5.6-sol'])
        self.assertTrue(all(o['status'] == 'completed' for o in result['cases'][0]['outputs']))
