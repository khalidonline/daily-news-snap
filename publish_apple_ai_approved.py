"""Publish owner-approved Apple local-AI explainer without rewriting."""
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

TITLE="ليش أبل تبي الذكاء الاصطناعي يشتغل عندك؟"
CARDS=[
{"kind":"info","title":"ليش أبل تفكر كذا؟","body":"تعودنا إن الذكاء الاصطناعي يشتغل من السحابة: ترسل طلبك لسيرفرات بعيدة وترجع لك النتيجة.","punch":"أبل تقول: ليش ما يشتغل جزء كبير منه عندك؟","claim_ids":["a1"],"image_query":"Mac Studio computer"},
{"kind":"story","title":"وش الفايدة؟","body":"كل ما اعتمدت على السحابة أكثر، زادت حاجتك للإنترنت وزادت التكلفة مع الاستخدام. وإذا اشتغل محليًا، يصير أسرع في بعض المهام وخصوصيتك أعلى.","punch":"جزء من الـAI يرجع لجهازك بدل السحابة.","claim_ids":["a2"],"image_query":"computer desk monitor"},
{"kind":"story","title":"وهنا يجي Mac Studio","body":"أبل رفعت Mac Studio الجديد للـAI المحلي: ذاكرة ضخمة وأداء أعلى وتشغيل نماذج كبيرة على الجهاز نفسه.","punch":"يعني جهاز على المكتب.. لكنه أقرب لمحطة AI صغيرة.","claim_ids":["a3"],"image_query":"Mac Studio desktop"},
{"kind":"story","title":"حتى أكثر من جهاز","body":"أبل تقول إنك تقدر تربط أكثر من Mac Studio مع بعض. وربط 4 أجهزة يرفع سرعة تشغيل نماذج AI مقارنة بجهاز واحد.","punch":"الفكرة مو جهاز أقوى وبس.. بل AI أقل اعتمادًا على السحابة.","claim_ids":["a4"],"image_query":"Thunderbolt cable computers"},
]
FALLBACK={
"Mac Studio computer":["Apple desktop computer","small desktop computer","computer workstation"],
"computer desk monitor":["computer desk","desktop computer desk","office computer monitor"],
"Mac Studio desktop":["compact desktop computer","Apple computer desktop","desktop computer"],
"Thunderbolt cable computers":["computer cable workstation","Thunderbolt cable","computer networking cable"],
}
def main():
    if os.environ.get("GITHUB_REPOSITORY")!="khalidonline/daily-news-snap" or os.environ.get("GITHUB_REF")!="refs/heads/main": raise ValueError("configured_main_required")
    now=datetime.now(timezone.utc)
    token=os.environ.get("DAILY_BUDGET_GITHUB_TOKEN") or os.environ["GITHUB_TOKEN"]
    ledger=Ledger(GitHubStore(os.environ["GITHUB_REPOSITORY"],token),limit_micro_usd=autopilot_daily_limit(now,os.environ.get("AUTOPILOT_DAILY_LIMIT_MICRO_USD","8000000")))
    agent=Agents(env=os.environ,ledger=ledger)
    sources=Sources(recovery=True,publication_only=True,image_memory=ImageMemory(GitHubJournal("autopilot-image-memory")))
    renderer=Renderer(agent,sources)
    package={"title":TITLE,"cards":[dict(c) for c in CARDS],
      "sources":[{"url":"https://www.apple.com/newsroom/2026/08/apple-introduces-new-mac-studio-with-m5-max-and-m5-ultra/"}],
      "candidate":{"id":"owner-approved-apple-local-ai-20260925","title":TITLE,"resolved_subject":{"name":"Mac Studio"}},
      "lane":"daily","expires_at":"2026-09-27T00:00:00+03:00","as_of":now.isoformat(),
      "editorial_feedback":[{"subject":"Owner approval","reason":"Exact owner-approved copy; no writer rewrite."}]}
    used=set(); hashes=set(); origins=set()
    for card in package["cards"]:
      chosen=None
      for q in [card["image_query"]]+FALLBACK[card["image_query"]]:
        rows=[r for r in sources.subject_images(q,q) if image_publication_eligible(r)]
        if not rows: continue
        accepted=renderer.check_source_images(package["candidate"],q,rows)
        for row in accepted:
          if row["asset_id"] in used or (row.get("sha256") and row["sha256"] in hashes) or (row.get("origin_key") and row["origin_key"] in origins): continue
          chosen=row; break
        if chosen: break
      if not chosen: raise ValueError("no_distinct_relevant_image_for_"+card["image_query"].replace(" ","_"))
      card["image"]=dict(chosen); used.add(chosen["asset_id"])
      if chosen.get("sha256"): hashes.add(chosen["sha256"])
      if chosen.get("origin_key"): origins.add(chosen["origin_key"])
    out=Path("apple-package-output"); paths=renderer(package,out)
    editorial=[p for p,c in zip(paths,package["cards"]) if c.get("kind")!="credits"]
    for i,path in enumerate(editorial):
      ident=f"card-{i}"; card=package["cards"][i]
      check=agent.run("image_check",{"subject":card["image_query"],"source_title":card["title"],"options":[{"asset_id":ident,"title":card["title"],"source_url":""}]},images=[path])
      if check.get("accepted_ids") != [ident]: raise ValueError("final_visual_check_failed_card_"+str(i+1))
    receipt=publish_package(package,paths)
    result={"status":"published","title":TITLE,"receipt":receipt}
    (out/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__": main()
