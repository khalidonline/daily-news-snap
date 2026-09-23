#!/usr/bin/env python3
"""Compare production reviewer and visual roles across Claude Opus and Sonnet.

The benchmark reuses frozen historical artifacts. It never writes production
readiness, Telegram, Bundle, or Snapchat state. All paid calls are made through
the same Agents implementation used by production, under one shared daily-budget
reservation.
"""
from __future__ import annotations

import copy
import json
import os
import time
from pathlib import Path
from typing import Any

from daily_budget import BudgetBlocked, GitHubStore, Ledger
from publishing_v2.autopilot.agents import Agents
from publishing_v2.autopilot.policy import REVIEW_CHECKS

MODELS = ("claude-opus-5", "claude-sonnet-5")
SHARED_RESERVATION_MICRO_USD = 1_500_000


class LocalLedger:
    """Bound paid calls inside the already-reserved experiment allowance."""

    def __init__(self, limit_micro_usd: int):
        self.limit_micro_usd = limit_micro_usd
        self.active: dict[str, int] = {}
        self.charged_micro_usd = 0
        self.sequence = 0

    def reserve(self, amount: int, bot: str):
        if type(amount) is not int or amount <= 0:
            raise BudgetBlocked("invalid experiment reservation")
        outstanding = sum(self.active.values())
        if self.charged_micro_usd + outstanding + amount > self.limit_micro_usd:
            raise BudgetBlocked(
                "reviewer/visual experiment cap reached",
                code="experiment_cap",
                limit=self.limit_micro_usd,
                requested=amount,
                charged=self.charged_micro_usd + outstanding,
            )
        self.sequence += 1
        token = f"local-{self.sequence}"
        self.active[token] = amount
        return token

    def settle(self, token, actual: int):
        if token not in self.active:
            raise BudgetBlocked("unknown experiment reservation")
        if type(actual) is not int or actual < 0:
            raise BudgetBlocked("invalid experiment settlement")
        self.active.pop(token)
        self.charged_micro_usd += actual
        if self.charged_micro_usd > self.limit_micro_usd:
            raise BudgetBlocked("experiment actual cost exceeded cap")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("json_object_required")
    return value


def resolve_agentic_images(root: Path, state: dict[str, Any]) -> list[Path]:
    paths = []
    for raw in state.get("paths", []):
        marker = "autopilot-output/"
        if marker not in raw:
            raise ValueError("unexpected_historical_path")
        relative = raw.split(marker, 1)[1]
        path = root / relative
        if not path.is_file():
            raise ValueError("historical_image_missing")
        paths.append(path)
    if not paths:
        raise ValueError("historical_images_required")
    return paths


def reviewer_cases(agentic_root: Path, replay_root: Path) -> list[dict[str, Any]]:
    daily = load_json(agentic_root / "daily.json")
    replay = load_json(replay_root / "result.json")

    daily_input = copy.deepcopy(daily["package"])
    daily_input["original_sources"] = copy.deepcopy(daily["sources"])
    daily_images = resolve_agentic_images(agentic_root, daily)

    replay_input = copy.deepcopy(replay["package"])
    replay_input["original_sources"] = copy.deepcopy(replay["package"].get("sources", []))
    replay_images = sorted(replay_root.glob("card-*.jpg"))
    if len(replay_images) != len(replay["package"].get("cards", [])):
        raise ValueError("replay_images_incomplete")

    return [
        {
            "id": "hadjar-shadow",
            "input": daily_input,
            "images": daily_images,
            "historical_review": copy.deepcopy(daily.get("review")),
        },
        {
            "id": "blackhawk-replay",
            "input": replay_input,
            "images": replay_images,
            "historical_review": copy.deepcopy(replay.get("review")),
        },
    ]


def option_from_image(image: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": image["asset_id"],
        "title": str(image.get("title", ""))[:250],
        "description": str(image.get("description", ""))[:900],
        "pixel_description": str(image.get("pixel_description", ""))[:600],
        "date_created": str(image.get("date_created", ""))[:100],
        "image_role": str(
            image.get("image_role", "subject illustration; event date requires review")
        )[:300],
    }


def visual_case(state: dict[str, Any], distractor_state: dict[str, Any], ident: str) -> dict[str, Any]:
    editorial = [copy.deepcopy(c) for c in state["package"]["cards"] if c.get("kind") != "credits"]
    expected = [c["image"]["asset_id"] for c in editorial]
    for card in editorial:
        card.pop("image", None)
        card.pop("public_attribution", None)

    catalog: dict[str, dict[str, Any]] = {}
    for card in state["package"]["cards"]:
        if card.get("kind") == "credits":
            continue
        image = card.get("image")
        if isinstance(image, dict) and isinstance(image.get("asset_id"), str):
            catalog[image["asset_id"]] = option_from_image(image)

    distractors = [
        c.get("image") for c in distractor_state["package"]["cards"]
        if c.get("kind") != "credits" and isinstance(c.get("image"), dict)
    ]
    if distractors:
        image = distractors[0]
        if image.get("asset_id") not in catalog:
            catalog[image["asset_id"]] = option_from_image(image)

    if not all(asset_id in catalog for asset_id in expected):
        raise ValueError("visual_expected_asset_missing")
    return {
        "id": ident,
        "input": {"cards": editorial, "options": list(catalog.values()), "repair": {}},
        "expected_ids": expected,
        "distractor_ids": [asset_id for asset_id in catalog if asset_id not in set(expected)],
    }


def visual_cases(agentic_root: Path) -> list[dict[str, Any]]:
    daily = load_json(agentic_root / "daily.json")
    local = load_json(agentic_root / "local.json")
    return [
        visual_case(daily, local, "hadjar-visual"),
        visual_case(local, daily, "national-day-visual"),
    ]


def reviewer_overall(decision: dict[str, Any] | None) -> bool | None:
    if not isinstance(decision, dict):
        return None
    checks = decision.get("checks")
    rows = decision.get("card_checks")
    if not isinstance(checks, dict) or not isinstance(rows, list):
        return False
    return (
        all(checks.get(key) is True for key in REVIEW_CHECKS)
        and all(
            isinstance(row, dict)
            and row.get("readable") is True
            and row.get("relevant") is True
            for row in rows
        )
    )


def run_agent(
    role: str,
    model: str,
    data: dict[str, Any],
    images: list[Path],
    ledger: LocalLedger,
    base_env: dict[str, str],
) -> dict[str, Any]:
    env = dict(base_env)
    env[f"AUTOPILOT_{role.upper()}_MODEL"] = model
    agent = Agents(env=env, ledger=ledger)
    started = time.monotonic()
    try:
        decision = agent.run(role, copy.deepcopy(data), images=images)
        status = "completed"
        error = None
    except Exception as exc:
        decision = None
        status = "failed"
        error = f"{type(exc).__name__}:{str(exc)[:160]}"
    elapsed_ms = round((time.monotonic() - started) * 1000)
    cost = sum(int(row.get("cost_micro_usd", 0)) for row in agent.receipts)
    return {
        "status": status,
        "decision": decision,
        "error": error,
        "elapsed_ms": elapsed_ms,
        "cost_micro_usd": cost,
        "receipts": copy.deepcopy(agent.receipts),
    }


def compare_reviewer(outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    opus = outputs.get("claude-opus-5", {}).get("decision")
    sonnet = outputs.get("claude-sonnet-5", {}).get("decision")
    if not isinstance(opus, dict) or not isinstance(sonnet, dict):
        return {"comparable": False}

    opus_checks = opus.get("checks", {})
    sonnet_checks = sonnet.get("checks", {})
    exact = [key for key in REVIEW_CHECKS if opus_checks.get(key) is sonnet_checks.get(key)]
    unsafe = [
        key for key in REVIEW_CHECKS
        if opus_checks.get(key) is False and sonnet_checks.get(key) is True
    ]
    conservative = [
        key for key in REVIEW_CHECKS
        if opus_checks.get(key) is True and sonnet_checks.get(key) is False
    ]
    return {
        "comparable": True,
        "exact_check_count": len(exact),
        "check_count": len(REVIEW_CHECKS),
        "unsafe_sonnet_passes": unsafe,
        "sonnet_extra_rejections": conservative,
        "opus_overall_pass": reviewer_overall(opus),
        "sonnet_overall_pass": reviewer_overall(sonnet),
        "same_overall_decision": reviewer_overall(opus) == reviewer_overall(sonnet),
        "card_checks_equal": opus.get("card_checks") == sonnet.get("card_checks"),
    }


def validate_visual(decision: dict[str, Any] | None, case: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(decision, dict):
        return {"valid": False, "exact": False, "reason": "no_decision"}
    ids = decision.get("image_ids")
    allowed = {row["asset_id"] for row in case["input"]["options"]}
    valid = (
        isinstance(ids, list)
        and len(ids) == len(case["expected_ids"])
        and all((item is None or item in allowed) for item in ids)
    )
    return {
        "valid": valid,
        "exact": valid and ids == case["expected_ids"],
        "selected_ids": ids if isinstance(ids, list) else None,
        "selected_distractors": (
            [item for item in ids if item in set(case["distractor_ids"])]
            if isinstance(ids, list)
            else []
        ),
    }


def reserve_shared_budget(env: dict[str, str]):
    repository = env.get("GITHUB_REPOSITORY", "").strip()
    token = (env.get("DAILY_BUDGET_GITHUB_TOKEN", "") or env.get("GITHUB_TOKEN", "")).strip()
    if not repository or not token:
        if env.get("GITHUB_ACTIONS") == "true":
            raise ValueError("shared_budget_credentials_required")
        return None, None
    ledger = Ledger(GitHubStore(repository, token))
    reservation = ledger.reserve(
        SHARED_RESERVATION_MICRO_USD,
        "manual:reviewer-visual-model-experiment",
    )
    return ledger, reservation


def run(agentic_root: Path, replay_root: Path, output: Path, env: dict[str, str]) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    shared_ledger, shared_token = reserve_shared_budget(env)
    local_ledger = LocalLedger(SHARED_RESERVATION_MICRO_USD)

    result: dict[str, Any] = {
        "schema_version": 1,
        "published": False,
        "production_changed": False,
        "shared_reservation_usd": SHARED_RESERVATION_MICRO_USD / 1_000_000,
        "reviewer": {"cases": []},
        "visual": {"cases": []},
    }

    try:
        for case in reviewer_cases(agentic_root, replay_root):
            outputs = {}
            for model in MODELS:
                outputs[model] = run_agent(
                    "reviewer", model, case["input"], case["images"], local_ledger, env
                )
                outputs[model]["overall_pass"] = reviewer_overall(outputs[model]["decision"])
            result["reviewer"]["cases"].append(
                {
                    "id": case["id"],
                    "historical_review": case["historical_review"],
                    "outputs": outputs,
                    "comparison": compare_reviewer(outputs),
                }
            )

        for case in visual_cases(agentic_root):
            outputs = {}
            for model in MODELS:
                outputs[model] = run_agent(
                    "visual", model, case["input"], [], local_ledger, env
                )
                outputs[model]["validation"] = validate_visual(outputs[model]["decision"], case)
            result["visual"]["cases"].append(
                {
                    "id": case["id"],
                    "expected_ids": case["expected_ids"],
                    "distractor_ids": case["distractor_ids"],
                    "outputs": outputs,
                }
            )
    finally:
        result["actual_cost_usd"] = round(local_ledger.charged_micro_usd / 1_000_000, 6)
        if shared_ledger is not None and shared_token is not None:
            shared_ledger.settle(shared_token, local_ledger.charged_micro_usd)

    reviewer_cases_result = result["reviewer"]["cases"]
    comparable = [row["comparison"] for row in reviewer_cases_result if row["comparison"].get("comparable")]
    result["reviewer"]["summary"] = {
        "case_count": len(reviewer_cases_result),
        "comparable_case_count": len(comparable),
        "unsafe_sonnet_passes": sum(len(row.get("unsafe_sonnet_passes", [])) for row in comparable),
        "same_overall_decisions": sum(row.get("same_overall_decision") is True for row in comparable),
        "exact_checks": sum(row.get("exact_check_count", 0) for row in comparable),
        "total_checks": sum(row.get("check_count", 0) for row in comparable),
    }

    visual_rows = result["visual"]["cases"]
    result["visual"]["summary"] = {
        model: {
            "exact_cases": sum(
                row["outputs"][model].get("validation", {}).get("exact") is True
                for row in visual_rows
            ),
            "case_count": len(visual_rows),
            "distractor_selections": sum(
                len(row["outputs"][model].get("validation", {}).get("selected_distractors", []))
                for row in visual_rows
            ),
        }
        for model in MODELS
    }

    for section in ("reviewer", "visual"):
        costs = {}
        latencies = {}
        for model in MODELS:
            rows = result[section]["cases"]
            costs[model] = sum(row["outputs"][model]["cost_micro_usd"] for row in rows) / 1_000_000
            completed = [
                row["outputs"][model]["elapsed_ms"]
                for row in rows if row["outputs"][model]["status"] == "completed"
            ]
            latencies[model] = round(sum(completed) / len(completed), 1) if completed else None
        result[section]["cost_usd"] = {k: round(v, 6) for k, v in costs.items()}
        result[section]["average_latency_ms"] = latencies

    (output / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "actual_cost_usd": result["actual_cost_usd"],
        "reviewer": result["reviewer"]["summary"],
        "visual": result["visual"]["summary"],
        "note": "No production routing, readiness, Telegram, Bundle, or Snapchat mutation.",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--agentic-root", type=Path, required=True)
    parser.add_argument("--replay-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("role-experiment-output"))
    args = parser.parse_args()
    run(args.agentic_root, args.replay_root, args.output, dict(os.environ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
