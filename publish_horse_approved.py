"""Publish approved Saudi horse/falcon-show explainer without rewriting."""
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

TITLE="ليش الخيل للحين لها مكانة خاصة عندنا؟"
CARDS=[
{"kind":"info","title":"الخيل حاضرة بتجربة حية","body":"معرض الصقور والصيد 2026 ما وقف عند الصقور. فيه تجربة خيل وفروسية تخلي الزوار يشوفونها ويتفاعلون معها عن قرب.","punch":"الفكرة: الموروث يصير شيء تعيشه مو بس تسمع عنه.","claim_ids":["h1"],"image_query":"Arabian horse Saudi"},
{"kind":"story","title":"ليش الخيل مهمة أصلًا؟","body":"الخيل ارتبطت عند أهل الجزيرة بالسفر والصيد والمهارة والمكانة. وعشان كذا علاقتها بالمجتمع أقدم من كونها رياضة.","punch":"هي جزء من قصة الناس قبل ما تكون بطولة.","claim_ids":["h2"],"image_query":"Arabian horse rider desert"},
{"kind":"story","title":"وش المختلف اليوم؟","body":"بدل ما تكون الفروسية قصة قديمة تنقال، صارت تجربة يشوفها الأطفال والشباب قدامهم: خيل، مهارات، وتفاعل مباشر.","punch":"الموروث إذا عاش قدامك.. يصير أقرب لك.","claim_ids":["h3"],"image_query":"horse riding family event"},
{"kind":"story","title":"وهذا اللي يفسر حضورها","body":"الخيل والصقور اجتمعوا تاريخيًا حول الرحلات والصحراء والصيد. والمعرض يجمعهم اليوم في مكان واحد بشكل أقرب للناس.","punch":"نفس الموروث.. لكن بطريقة تناسب جيل اليوم.","claim_ids":["h4"],"image_query":"Arabian horse falcon desert"},
]
FALLBACK={
"Arabian horse Saudi":["Arabian horse","Saudi Arabian horse","Arabian stallion"],
"Arabian horse rider desert":["Arabian horse rider","horse rider desert","equestrian Arabian horse"],
"horse riding family event":["horse riding event","equestrian event","horse show audience"],
"Arabian horse falcon desert":["Arabian horse desert","horse and falcon","equestrian desert"],
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
      "sources":[{"url":"https://www.spa.gov.sa/w516368"}],
      "candidate":{"id":"owner-approved-horse-20260925","title":TITLE,"resolved_subject":{"name":"Arabian horse"}},
      "lane":"local","expires_at":"2026-09-27T00:00:00+03:00","as_of":now.isoformat(),
      "editorial_feedback":[{"subject":"Owner approval","reason":"Owner selected horse package; simple Saudi style."}]}
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
    out=Path("horse-package-output"); paths=renderer(package,out)
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
