#!/usr/bin/env python3
"""Ten-category local proof of Story cost controls; never calls external APIs."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

import story_cost_report as scr
import story_editorial_runtime as ser


PILOT_STORIES = (
    ("city", "Pilot city transformation"),
    ("company", "Pilot company transformation"),
    ("person", "Pilot founder story"),
    ("historical", "Pilot historical event"),
    ("policy", "Pilot regulated policy story"),
    ("product", "Pilot product story"),
    ("finance", "Pilot finance story"),
    ("infrastructure", "Pilot infrastructure story"),
    ("heritage", "Pilot Saudi heritage story"),
    ("global_business", "Pilot global business story"),
)


def _brief(label: str) -> dict:
    return {
        "title": f"Proof {label}",
        "caption": "Local cost-control proof only",
        "frames": [
            {
                "heading": f"Beat {i}",
                "text": f"Distinct local proof narrative beat {i} for {label} with enough context to pass deterministic checks.",
                "punch": f"Payoff {i}",
                "subject_kind": "company",
                "image_keywords": [f"proof subject {i}"],
                "image_keywords_ar": [f"موضوع تجريبي {i}"],
            }
            for i in range(1, 7)
        ],
        "sources": ["Local proof fixture", "Deterministic test data"],
        "image_queries": ["local proof"],
        "image_queries_ar": ["اختبار محلي"],
        "image_prompt": "",
    }


class _LocalStoryBot:
    SYSTEM_PROMPT = "local pilot prompt {n}"
    STORY_MODEL = "local-proof-model"
    STORY_FRAMES = 6

    def __init__(self, category: str):
        self.category = category
        self.calls = 0
        self._LAST_EDITORIAL_USAGE = {}

    def research(self, story: str) -> dict:
        self.calls += 1
        self._LAST_EDITORIAL_USAGE = {
            "message_id": f"local-{self.category}-{self.calls}",
            "input_tokens": 100,
            "output_tokens": 100,
        }
        return _brief(self.category)


def run_pilot(output: Path | None = None) -> dict:
    saved = {key: os.environ.get(key) for key in (
        "STORY_BRIEF_ROOT", "STORY_COST_STATE_ROOT", "STORY_OPERATION_MODE",
        "STORY_REGENERATION_NONCE", "POST_TO_SNAPCHAT",
    )}
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            os.environ["STORY_BRIEF_ROOT"] = str(root / "briefs")
            os.environ["STORY_COST_STATE_ROOT"] = str(root / "state")
            os.environ["POST_TO_SNAPCHAT"] = "0"
            os.environ.pop("STORY_REGENERATION_NONCE", None)

            details = []
            for category, story in PILOT_STORIES:
                sb = _LocalStoryBot(category)
                ser.configure(sb)

                os.environ["STORY_OPERATION_MODE"] = "auto"
                first = sb.research(story)
                second = sb.research(story)
                calls_after_auto_rerun = sb.calls

                os.environ["STORY_OPERATION_MODE"] = "visual_only"
                third = sb.research(story)
                calls_after_visual_only = sb.calls

                details.append({
                    "category": category,
                    "story": story,
                    "first_equals_rerun": first == second,
                    "rerun_equals_visual_only": second == third,
                    "paid_calls": sb.calls,
                    "auto_rerun_added_calls": calls_after_auto_rerun - 1,
                    "visual_only_added_calls": calls_after_visual_only - calls_after_auto_rerun,
                })

            report = scr.summarize(root / "state" / "model_usage.jsonl", root / "missing-notifications.jsonl")
            result = {
                "proof_only": True,
                "publication_quality_evaluated": False,
                "external_api_calls": 0,
                "snapchat_posts": 0,
                "categories": len(details),
                "all_auto_reruns_zero_paid_calls": all(item["auto_rerun_added_calls"] == 0 for item in details),
                "all_visual_only_zero_paid_calls": all(item["visual_only_added_calls"] == 0 for item in details),
                "details": details,
                "report": report,
            }
            if output is not None:
                output = Path(output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return result
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_pilot(args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["report"]["paid_editorial_calls"] != len(PILOT_STORIES):
        raise SystemExit("pilot failed: expected exactly one local editorial call per story")
    if not result["all_auto_reruns_zero_paid_calls"]:
        raise SystemExit("pilot failed: ordinary rerun added an editorial call")
    if not result["all_visual_only_zero_paid_calls"]:
        raise SystemExit("pilot failed: visual_only added an editorial call")


if __name__ == "__main__":
    main()
