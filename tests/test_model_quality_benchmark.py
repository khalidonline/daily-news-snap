import unittest
from pathlib import Path

import yaml
from model_quality_benchmark import rank_candidates, weighted_quality


WEIGHTS = {"arabic": 0.35, "accuracy": 0.35, "snapchat": 0.2, "format": 0.1}


class ModelQualityBenchmarkTests(unittest.TestCase):
    def test_weighted_quality_uses_declared_dimensions(self):
        scores = {"arabic": 90, "accuracy": 100, "snapchat": 80, "format": 70}
        self.assertEqual(weighted_quality(scores, WEIGHTS), 89.5)

    def test_cheapest_candidate_wins_only_after_quality_and_validation_gates(self):
        benchmark = {
            "weights": WEIGHTS,
            "baseline": {
                "id": "current",
                "quality": {"arabic": 90, "accuracy": 90, "snapchat": 90, "format": 90},
            },
            "candidates": [
                {
                    "id": "cheap-low-quality",
                    "validation_passed": True,
                    "cost_usd": 0.01,
                    "latency_ms": 100,
                    "quality": {"arabic": 80, "accuracy": 80, "snapchat": 80, "format": 80},
                },
                {
                    "id": "cheap-valid",
                    "validation_passed": True,
                    "cost_usd": 0.04,
                    "latency_ms": 900,
                    "quality": {"arabic": 92, "accuracy": 92, "snapchat": 92, "format": 92},
                },
                {
                    "id": "invalid",
                    "validation_passed": False,
                    "cost_usd": 0.001,
                    "latency_ms": 50,
                    "quality": {"arabic": 100, "accuracy": 100, "snapchat": 100, "format": 100},
                },
                {
                    "id": "expensive-valid",
                    "validation_passed": True,
                    "cost_usd": 0.09,
                    "latency_ms": 200,
                    "quality": {"arabic": 95, "accuracy": 95, "snapchat": 95, "format": 95},
                },
            ],
        }

        result = rank_candidates(benchmark)

        self.assertEqual(result["baseline_quality"], 90.0)
        self.assertEqual([row["id"] for row in result["eligible"]], ["cheap-valid", "expensive-valid"])
        self.assertEqual(result["winner"]["id"], "cheap-valid")
        self.assertEqual(
            {row["id"]: row["reason"] for row in result["rejected"]},
            {"cheap-low-quality": "quality_below_baseline", "invalid": "validation_failed"},
        )

    def test_equal_cost_prefers_lower_latency_then_higher_quality(self):
        benchmark = {
            "weights": {"accuracy": 1.0},
            "baseline": {"id": "current", "quality": {"accuracy": 80}},
            "candidates": [
                {"id": "slow", "validation_passed": True, "cost_usd": 0.02, "latency_ms": 500, "quality": {"accuracy": 99}},
                {"id": "fast", "validation_passed": True, "cost_usd": 0.02, "latency_ms": 100, "quality": {"accuracy": 85}},
            ],
        }
        self.assertEqual(rank_candidates(benchmark)["winner"]["id"], "fast")

    def test_benchmark_workflow_is_manual_only_and_has_no_production_secrets(self):
        path = Path(".github/workflows/model-quality-benchmark.yml")
        text = path.read_text(encoding="utf-8")
        workflow = yaml.load(text, Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertNotIn("secrets.", text)
        self.assertNotIn("POST_TO_SNAPCHAT", text)
        self.assertIn("python model_quality_benchmark.py", text)


if __name__ == "__main__":
    unittest.main()
