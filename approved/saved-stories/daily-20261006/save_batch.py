"""Save exact final packages published on 2026-10-06.

No production, upload, daily repost, or paid model request. Bundle inventory,
POSTED receipts, cost evidence, and a two-operation quota reserve are checked.
Bab el-Mandeb remains held because its durable source receipt is SENDING.
"""
import json, os
from datetime import datetime, timezone
from pathlib import Path
from daily_budget import GitHubStore, day_key
from publishing_v2.bundle_api import BundleError, GitHubJournal
from publishing_v2.saved_story_api import SavedClient, SavedJournal, now, save_story, validate_archive

BASE=Path("approved/saved-stories/daily-20261006")
ORDER=["instagram-20261006","energy-pipeline-20261006","energy-google-20261006"]
RESERVE=2
BAB_ID="487cd9bf6efcc2f335787afcae61f14d32bf783fa131aecdd910b741f770772c"

class StateFile(GitHubJournal):
    def __init__(self,path):
        super().__init__("archive-batch-20261006"); self.path="/contents/"+path

def check_live(client,rows):
    for row in rows:
        uploads=row.get("group_upload_ids",[row["upload_id"]])
        if row.get("group_upload_ids"): client.confirm_group(row["post_id"],uploads)
        live=client.call("/post/"+row["post_id"]); snap=(live.get("data") or {}).get("SNAPCHAT") or {}
        if (live.get("id")!=row["post_id"] or live.get("teamId")!=client.team
            or live.get("status")!="POSTED" or live.get("deletedAt")
            or snap.get("type","STORY")!="STORY" or snap.get("uploadIds")!=uploads
            or row["upload_id"] not in uploads):
            raise BundleError("source_live_mismatch")

def main():
    client=SavedClient(); client.check()
    audit=StateFile("saved-story-audits/daily-20261006.json")
    report=audit.read() or {"started_at":now(),"results":[],"paid_model_requests":0,"reserve":RESERVE}
    store=GitHubStore(os.environ["GITHUB_REPOSITORY"],os.environ["GITHUB_TOKEN"])
    ledgers=[]
    for day in sorted({"2026-10-06",day_key()}):
        _,row=store.read(day)
        charged=sum(e["charged_micro_usd"] for e in row.get("entries",{}).values()) if row is not None else None
        if charged is not None and charged>3_000_000: raise BundleError("daily_budget_exceeded")
        ledgers.append({"day":day,"ledger_present":row is not None,"recorded_micro_usd":charged})
    report["budget_checks"]=ledgers; report["missing_ledger_not_zero"]=True
    audit.save(report); print("BUDGET "+json.dumps(ledgers),flush=True)

    prepared=[]
    for name in ORDER:
        ap=BASE/(name+".json"); approval=json.loads(ap.read_text()); current=datetime.now(timezone.utc)
        if datetime.fromisoformat(approval["not_before"].replace("Z","+00:00"))>current: raise BundleError("archive_not_before")
        if datetime.fromisoformat(approval["expires_at"].replace("Z","+00:00"))<=current: raise BundleError("archive_approval_expired")
        source=GitHubJournal(approval["identity"]).read()
        identity,title,rows=validate_archive(approval,source); check_live(client,rows)
        uploads=[r["upload_id"] for r in rows]; found=client.find(identity,title,uploads)
        if len(found)>1: raise BundleError("multiple_existing_saved_stories")
        journal=SavedJournal(identity); prior=journal.read()
        if prior and not prior.get("post_id") and prior.get("status")!="POSTED": raise BundleError("ambiguous_saved_story_intent")
        prepared.append((name,ap,approval,identity,title,rows,uploads,journal,prior))

    new_count=sum(1 for item in prepared if not item[8])
    report["quota_before"]=client.ensure_capacity(new_count+RESERVE)
    report["provider_matches_before"]={item[0]:client.find(item[3],item[4],item[6]) for item in prepared}
    audit.save(report)
    remaining_new=new_count
    for name,ap,approval,identity,title,rows,uploads,journal,prior in prepared:
        needs_create=not prior
        if needs_create: client.ensure_capacity(remaining_new+RESERVE)
        validate_archive(approval,GitHubJournal(identity).read()); check_live(client,rows)
        result=save_story(client,journal,identity,title,uploads)
        confirmed=client.confirm(result["post_id"],title,uploads)
        snap=(confirmed.get("externalData") or {}).get("SNAPCHAT") or {}
        if not snap.get("id") or len(snap.get("mediaIds") or [])!=len(uploads):
            raise BundleError("saved_story_id_or_media_count_missing")
        result.update(approval=str(ap),package=name,scope="SAVED_STORY_ONLY",source_identity=identity,media_sha256=approval["media_sha256"])
        journal.save(result)
        backlog_journal=StateFile("saved-story-backlog.json"); backlog=backlog_journal.read(); entries=backlog.setdefault("packages",[])
        entry=next((x for x in entries if x.get("identity")==identity),None)
        if entry is None:
            entry={"identity":identity,"manifest":approval["manifest"],"title":title,"card_count":len(rows)}; entries.insert(0,entry)
        entry.update(status="POSTED",publication_status="POSTED",archive_status="POSTED",saved_story_id=snap["id"],saved_post_id=result["post_id"],saved_title=title,saved_receipt_path="saved-story-receipts/"+identity+".json",saved_confirmed_at=now(),saved_card_count=len(rows),archive_approval=str(ap))
        backlog["updated_at"]=now(); backlog_journal.save(backlog)
        row={"package":name,"title":title,"status":"POSTED","saved_story_id":snap["id"],"post_id":result["post_id"],"reused":prior.get("status")=="POSTED"}
        report["results"]=[x for x in report["results"] if x["package"]!=name]+[row]
        if needs_create: remaining_new-=1
        audit.save(report); print("SAVED "+json.dumps(row,ensure_ascii=False),flush=True)

    bab=GitHubJournal(BAB_ID).read()
    if bab.get("1",{}).get("status")!="POSTED":
        backlog_journal=StateFile("saved-story-backlog.json"); backlog=backlog_journal.read(); entries=backlog.setdefault("packages",[])
        entry=next((x for x in entries if x.get("identity")==BAB_ID),None)
        if entry is None:
            entry={"identity":BAB_ID,"package":"bab-mandeb-20261006","manifest":"approved/bab-mandeb-20261006/manifest.json","title":"أخبار اليمن… ليه باب المندب مهم؟","card_count":1}; entries.insert(0,entry)
        entry.update(status="HOLD_SOURCE_RECEIPT_NOT_POSTED",publication_status=bab.get("1",{}).get("status","UNKNOWN"),archive_status="NOT_SENT",note="Durable source receipt is not POSTED; no Saved Story request created.")
        backlog["updated_at"]=now(); backlog_journal.save(backlog)
        report["held"]={"package":"bab-mandeb-20261006","reason":"source receipt "+bab.get("1",{}).get("status","UNKNOWN"),"saved_request_created":False}
    report["quota_after"]=client.ensure_capacity(RESERVE); report["completed_at"]=now(); audit.save(report)
    print("COMPLETE "+json.dumps(report,ensure_ascii=False),flush=True)

if __name__=="__main__": main()
