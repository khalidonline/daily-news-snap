"""Recover today's pre-research held Local shadow into a fresh shadow slot.

This never touches a passed Daily package and never publishes. It is intended only
for a Local attempt that stopped before research after candidate timing rejection.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from daily_budget import GitHubStore, Ledger, autopilot_daily_limit, day_key
from publishing_v2.autopilot.agents import Agents
from publishing_v2.autopilot.candidate_memory import CandidateMemory
from publishing_v2.autopilot.pipeline import Pipeline
from publishing_v2.autopilot.published_memory import PublishedMemory
from publishing_v2.autopilot.runtime import Renderer, engine_id, shadow_record
from publishing_v2.autopilot.sources import Sources
from publishing_v2.bundle_api import GitHubJournal
from publishing_v2.primary_images import ImageMemory


def main():
    if os.environ.get("GITHUB_REPOSITORY") != "khalidonline/daily-news-snap":
        raise ValueError("configured_repository_required")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("main_branch_required")

    now = lambda: datetime.now(timezone.utc)
    engine = engine_id()
    today = day_key(now())
    readiness_journal = GitHubJournal("autopilot-readiness")
    readiness = readiness_journal.read()

    daily = readiness.get("daily", {})
    local = readiness.get("local", {})
    if (daily.get("engine") == engine and daily.get("status") in {"shadow_passed", "published"}
            and local.get("engine") == engine and local.get("status") in {"shadow_passed", "published"}):
        print(json.dumps({"status": "already_ready", "engine": engine}))
        return 0

    if daily.get("engine") != engine or daily.get("status") not in {"shadow_passed", "published"}:
        print(json.dumps({"status": "daily_not_ready", "engine": engine}))
        return 0

    original_slot = f"autopilot-{today}-local-shadow-{engine[:16]}"
    original = GitHubJournal(original_slot).read()
    if not original or original.get("status") != "held":
        print(json.dumps({"status": "no_recoverable_local_hold", "slot": original_slot}))
        return 0
    audit = original.get("audit", [])
    if any(row.get("event") in {"selected", "researched", "drafted", "review_passed"} for row in audit):
        print(json.dumps({"status": "held_after_paid_content_stage", "slot": original_slot}))
        return 0

    retry_slot = f"autopilot-{today}-local-shadow-recovery-{engine[:12]}"
    retry_store = GitHubJournal(retry_slot)
    existing = retry_store.read()
    if existing and existing.get("status") in {"shadow_passed", "held"}:
        result = existing
    else:
        token = os.environ.get("DAILY_BUDGET_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
        ledger = Ledger(GitHubStore(os.environ["GITHUB_REPOSITORY"], token),
                        limit_micro_usd=autopilot_daily_limit(
                            now(), os.environ.get("AUTOPILOT_DAILY_LIMIT_MICRO_USD", "8000000")))
        agent = Agents(env=os.environ, ledger=ledger)
        sources = Sources(recovery=True, publication_only=True,
                          image_memory=ImageMemory(GitHubJournal("autopilot-image-memory")))
        published_memory = PublishedMemory(GitHubJournal("autopilot-published-memory"), now)
        published_memory.import_manual(Path("approved"), GitHubJournal)
        candidate_memory = CandidateMemory(GitHubJournal("autopilot-candidate-memory"), now)
        pipeline = Pipeline(
            agent=agent,
            sources=sources,
            render=Renderer(agent, sources),
            store=retry_store,
            publish=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("recovery_never_publishes")),
            output=Path("autopilot-output/local-recovery"),
            now=now,
            engine=engine,
            candidate_memory=candidate_memory,
            published_memory=published_memory,
            excluded_candidate_ids=set(),
        )
        result = pipeline.run("local", "shadow", rollout_verified=False)

    if result.get("status") == "shadow_passed":
        state = readiness_journal.read()
        state["local"] = shadow_record(result, engine, retry_slot)
        readiness_journal.save(state)
        print(json.dumps({"status": "local_shadow_passed", "slot": retry_slot,
                          "title": result.get("package", {}).get("title")}, ensure_ascii=False))
        return 0

    print(json.dumps({"status": result.get("status", "unknown"),
                      "reason": result.get("reason"), "slot": retry_slot}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
