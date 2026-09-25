"""Publish owner-approved Saudi defense technology explainer without rewriting."""
import json, os
from datetime import datetime, timezone
from pathlib import Path

from daily_budget import GitHubStore, Ledger, autopilot_daily_limit
from publishing_v2.autopilot.agents import Agents
from publishing_v2.autopilot.runtime import Renderer, publish_package
from publishing_v2.autopilot.sources import Sources
from publishing_v2.bundle_api import GitHubJournal
from publishing_v2.primary_images import ImageMemory
from publishing_v2.publication import image_publication_eligible

TITLE = "ليش الدفاع قاعد يتغير؟"

CARDS = [
    {
        "kind":"info",
        "title":"ليش الدفاع قاعد يتغير؟",
        "body":"إذا سمعت «تطوير دفاع» يمكن أول شيء يجي ببالك طيارات أو دبابات جديدة. لكن الحروب اليوم تغيرت كثير.",
        "punch":"صار السؤال بعد: وش نقدر ننتجه ونطوره بأنفسنا؟",
        "claim_ids":["c1"],
        "image_query":"fighter aircraft",
    },
    {
        "kind":"story",
        "title":"المسيّرات غيرت اللعبة",
        "body":"أحد أكبر الأشياء اللي غيرت شكل الحرب هو المسيّرات. لأنها أعطت الجيوش خيار جديد: منصة أصغر وأرخص نسبيًا من بعض الطائرات المأهولة.",
        "punch":"وهذا غير طريقة التفكير في الدفاع.",
        "claim_ids":["c2"],
        "image_query":"military drone UAV",
    },
    {
        "kind":"story",
        "title":"كل هجوم يحتاج دفاع",
        "body":"إذا زادت المسيّرات، تحتاج أنظمة تكتشفها وتتبعها وتوقفها. وإذا صارت الهجمات أسرع، لازم تكون الصيانة وقطع الغيار أقرب وأسرع.",
        "punch":"عشان كذا التصنيع المحلي صار أهم.",
        "claim_ids":["c3"],
        "image_query":"modern surveillance radar",
    },
    {
        "kind":"story",
        "title":"هنا يجي التصنيع المحلي",
        "body":"توطين الصناعات العسكرية ما يعني إن كل شيء يتصنع محليًا من أول يوم. الفكرة إن جزء أكبر من الصناعة والصيانة والتطوير يصير داخل البلد.",
        "punch":"القدرة المحلية تكبر مع الوقت.",
        "claim_ids":["c4"],
        "image_query":"electronics manufacturing assembly line",
    },
    {
        "kind":"story",
        "title":"وش قاعد يصير بالسعودية؟",
        "body":"السعودية وقعت اتفاقات لتوطين صناعات عسكرية، ومنها مشاريع مرتبطة بالطائرات بدون طيار وتقنيات التحكم والذكاء الاصطناعي.",
        "punch":"الاتجاه مو شراء معدات وبس.. بل بناء صناعة حولها.",
        "claim_ids":["c5"],
        "image_query":"Saudi Arabia flag",
    },
    {
        "kind":"story",
        "title":"الفرق وقت الأزمة",
        "body":"وقت الأزمات ما يكفي يكون عندك معدات قوية. الأهم بعد: هل عندك قطع غيار؟ هل تقدر تصلحها؟ وهل عندك ناس يعرفون يشغلونها ويطورونها؟",
        "punch":"هنا الفرق بين امتلاك السلاح وامتلاك القدرة.",
        "claim_ids":["c6"],
        "image_query":"aircraft maintenance mechanic",
    },
]

QUERY_FALLBACKS = {
    "fighter aircraft":["military aircraft","fighter jet aircraft","jet aircraft"],
    "military drone UAV":["unmanned aerial vehicle","drone aircraft","UAV aircraft"],
    "modern surveillance radar":["radar antenna close up","radar station","surveillance radar"],
    "electronics manufacturing assembly line":["electronics factory assembly line","circuit board manufacturing","industrial assembly line"],
    "Saudi Arabia flag":["Saudi flag","flag of Saudi Arabia"],
    "aircraft maintenance mechanic":["aircraft maintenance hangar mechanic","airplane maintenance technician","aircraft mechanic"],
}

def main():
    if os.environ.get("GITHUB_REPOSITORY") != "khalidonline/daily-news-snap":
        raise ValueError("configured_repository_required")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("main_branch_required")

    now = datetime.now(timezone.utc)
    token = os.environ.get("DAILY_BUDGET_GITHUB_TOKEN") or os.environ["GITHUB_TOKEN"]
    ledger = Ledger(GitHubStore(os.environ["GITHUB_REPOSITORY"], token),
                    limit_micro_usd=autopilot_daily_limit(now, os.environ.get("AUTOPILOT_DAILY_LIMIT_MICRO_USD","8000000")))
    agent = Agents(env=os.environ, ledger=ledger)
    sources = Sources(recovery=True, publication_only=True,
                      image_memory=ImageMemory(GitHubJournal("autopilot-image-memory")))
    renderer = Renderer(agent, sources)

    package = {
        "title": TITLE,
        "cards": [dict(c) for c in CARDS],
        "sources": [
            {"url":"https://www.spa.gov.sa/en/N2511525"},
            {"url":"https://www.spa.gov.sa/N2511598"},
        ],
        "candidate": {
            "id":"owner-approved-defense-tech-20260925",
            "title":TITLE,
            "resolved_subject":{"name":"defense technology"},
        },
        "lane":"daily",
        "expires_at":"2026-09-27T00:00:00+03:00",
        "as_of":now.isoformat(),
        "editorial_feedback":[{"subject":"Owner approval","reason":"Exact owner-approved copy; no writer rewrite."}],
    }

    used_assets, used_hashes, used_origins = set(), set(), set()
    for card in package["cards"]:
        chosen = None
        for query in [card["image_query"]] + QUERY_FALLBACKS[card["image_query"]]:
            rows = [r for r in sources.subject_images(query, query) if image_publication_eligible(r)]
            if not rows:
                continue
            accepted = renderer.check_source_images(package["candidate"], query, rows)
            for row in accepted:
                if row["asset_id"] in used_assets:
                    continue
                if row.get("sha256") and row["sha256"] in used_hashes:
                    continue
                if row.get("origin_key") and row["origin_key"] in used_origins:
                    continue
                chosen = row
                break
            if chosen:
                break
        if not chosen:
            raise ValueError("no_distinct_relevant_image_for_" + card["image_query"].replace(" ","_"))
        card["image"] = dict(chosen)
        used_assets.add(chosen["asset_id"])
        if chosen.get("sha256"): used_hashes.add(chosen["sha256"])
        if chosen.get("origin_key"): used_origins.add(chosen["origin_key"])

    out = Path("defense-package-output")
    paths = renderer(package, out)

    # Final pixel pass per card. Generic illustrations do not need to depict
    # a Saudi event; they must truthfully illustrate that card's concept.
    editorial = [p for p, c in zip(paths, package["cards"]) if c.get("kind") != "credits"]
    for i, path in enumerate(editorial):
        card = package["cards"][i]
        ident = f"card-{i}"
        check = agent.run("image_check", {
            "subject":card["image_query"],
            "source_title":card["title"],
            "options":[{"asset_id":ident,"title":card["title"],"source_url":""}],
        }, images=[path])
        if check.get("accepted_ids") != [ident]:
            raise ValueError("final_visual_check_failed_card_" + str(i + 1))

    receipt = publish_package(package, paths)
    result = {"status":"published","title":TITLE,"receipt":receipt,
              "cards":[{"title":c["title"],"image":c.get("image",{}).get("asset_id")} for c in package["cards"]]}
    (out/"result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
