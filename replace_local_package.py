"""Delete today's weak Local package and publish one fresh Local replacement.

Uses a separate replacement slot. It never regenerates or republishes Daily.
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
from publishing_v2.autopilot.runtime import Renderer, engine_id, publish_package
from publishing_v2.autopilot.sources import Sources
from publishing_v2.bundle_api import BundleClient, GitHubJournal
from publishing_v2.primary_images import ImageMemory

BAHA_POST_IDS = [
    "ba93d598-881c-43f5-afc3-eca5d217811c",
    "e39efcae-961b-4a35-970a-acf6fa5dd7a4",
    "e7ae779f-025a-4058-997c-b2fafea9bf25",
]

def main():
    if os.environ.get("GITHUB_REPOSITORY") != "khalidonline/daily-news-snap":
        raise ValueError("configured_repository_required")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("main_branch_required")

    client = BundleClient()
    client.check()
    deleted = []
    for post_id in BAHA_POST_IDS:
        try:
            client.call("/post/" + post_id, "DELETE")
            deleted.append(post_id)
        except Exception as exc:
            # Fail closed before publishing a replacement if deletion is uncertain.
            print(json.dumps({"status":"delete_failed","post_id":post_id,"error":type(exc).__name__}))
            return 1

    now = lambda: datetime.now(timezone.utc)
    engine = engine_id()
    today = day_key(now())
    token = os.environ.get("DAILY_BUDGET_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    ledger = Ledger(GitHubStore(os.environ["GITHUB_REPOSITORY"], token),
                    limit_micro_usd=autopilot_daily_limit(
                        now(), os.environ.get("AUTOPILOT_DAILY_LIMIT_MICRO_USD", "8000000")))

    readiness = GitHubJournal("autopilot-readiness").read()
    daily_slot = readiness.get("daily", {}).get("slot")
    daily_state = GitHubJournal(daily_slot).read() if daily_slot else {}
    daily_id = daily_state.get("package", {}).get("candidate", {}).get("id")
    excluded = {daily_id} if daily_id else set()

    published_memory = PublishedMemory(GitHubJournal("autopilot-published-memory"), now)
    published_memory.import_manual(Path("approved"), GitHubJournal)
    candidate_memory = CandidateMemory(GitHubJournal("autopilot-candidate-memory"), now)
    agent = Agents(env=os.environ, ledger=ledger)
    sources = Sources(recovery=True, publication_only=True,
                      image_memory=ImageMemory(GitHubJournal("autopilot-image-memory")))

    slot = f"autopilot-{today}-local-replacement-live-{engine[:12]}"
    store = GitHubJournal(slot)
    existing = store.read()
    if existing and existing.get("status") == "published":
        print(json.dumps({"status":"already_published","slot":slot,
                          "receipt":existing.get("receipt")}, ensure_ascii=False))
        return 0

    pipeline = Pipeline(
        agent=agent,
        sources=sources,
        render=Renderer(agent, sources),
        store=store,
        publish=publish_package,
        output=Path("replacement-output/local"),
        now=now,
        engine=engine,
        candidate_memory=candidate_memory,
        published_memory=published_memory,
        excluded_candidate_ids=excluded,
    )
    result = pipeline.run("local", "live", rollout_verified=True)
    Path("replacement-output").mkdir(exist_ok=True)
    Path("replacement-output/result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    print(json.dumps({
        "deleted": deleted,
        "status": result.get("status"),
        "title": result.get("package", {}).get("title"),
        "reason": result.get("reason"),
        "receipt": result.get("receipt"),
        "slot": slot,
    }, ensure_ascii=False))
    return 0 if result.get("status") == "published" else 1

if __name__ == "__main__":
    raise SystemExit(main())
