#!/usr/bin/env python3
"""Rank frozen model outputs by quality gate, cost, and latency.

This command never calls a model. Human or automated evaluators prepare a
frozen JSON comparison first; this script applies the provider-neutral policy.
"""

import argparse
import json
from pathlib import Path
from typing import Any


def weighted_quality(scores: dict[str, Any], weights: dict[str, Any]) -> float:
    if not weights:
        raise ValueError("weights must not be empty")
    missing = set(weights) - set(scores)
    if missing:
        raise ValueError(f"quality is missing weighted dimensions: {sorted(missing)}")
    total_weight = sum(float(value) for value in weights.values())
    if total_weight <= 0:
        raise ValueError("weights must total more than zero")
    score = sum(float(scores[key]) * float(weight) for key, weight in weights.items())
    return round(score / total_weight, 4)


def rank_candidates(benchmark: dict[str, Any]) -> dict[str, Any]:
    weights = benchmark["weights"]
    baseline_quality = weighted_quality(benchmark["baseline"]["quality"], weights)
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for candidate in benchmark.get("candidates", []):
        row = dict(candidate)
        row["quality_score"] = weighted_quality(candidate["quality"], weights)
        if not candidate.get("validation_passed", False):
            row["reason"] = "validation_failed"
            rejected.append(row)
        elif row["quality_score"] < baseline_quality:
            row["reason"] = "quality_below_baseline"
            rejected.append(row)
        else:
            eligible.append(row)

    eligible.sort(
        key=lambda row: (
            float(row["cost_usd"]),
            float(row["latency_ms"]),
            -float(row["quality_score"]),
            str(row["id"]),
        )
    )
    return {
        "baseline_id": benchmark["baseline"]["id"],
        "baseline_quality": baseline_quality,
        "winner": eligible[0] if eligible else None,
        "eligible": eligible,
        "rejected": rejected,
    }


def markdown_summary(result: dict[str, Any]) -> str:
    lines = [
        "## Model quality/cost benchmark",
        "",
        f"Baseline: `{result['baseline_id']}` ({result['baseline_quality']:.2f})",
        "",
    ]
    winner = result["winner"]
    if winner:
        lines.append(
            f"Winner: `{winner['id']}` — quality {winner['quality_score']:.2f}, "
            f"cost ${float(winner['cost_usd']):.4f}, latency {float(winner['latency_ms']):.0f} ms"
        )
    else:
        lines.append("Winner: none; no candidate matched the current quality baseline.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Frozen candidate JSON")
    parser.add_argument("--output", type=Path, help="Write full ranking JSON")
    parser.add_argument("--summary", type=Path, help="Write Markdown summary")
    args = parser.parse_args()

    benchmark = json.loads(args.input.read_text(encoding="utf-8"))
    result = rank_candidates(benchmark)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.summary:
        args.summary.write_text(markdown_summary(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
