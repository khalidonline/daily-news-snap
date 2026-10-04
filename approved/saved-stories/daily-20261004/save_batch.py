"""One authorized archive batch; exact published bytes, no production or upload."""
import json,os
from pathlib import Path
from datetime import datetime,timezone
from publishing_v2.bundle_api import GitHubJournal,BundleError
from publishing_v2.saved_story_api import SavedClient,SavedJournal,save_story,validate_archive,now
from daily_budget import GitHubStore,day_key
BASE=Path('approved/saved-stories/daily-20261004')
ORDER=['dates-final-20261004','almarai-20261004']
class StateFile(GitHubJournal):
 def __init__(self,path):
  super().__init__('archive-batch-20261004');self.path='/contents/'+path

def check_live(c,rows):
 for r in rows:
  if r.get('group_upload_ids'): c.confirm_group(r['post_id'],r['group_upload_ids'])
  live=c.call('/post/'+r['post_id']);snap=(live.get('data') or {}).get('SNAPCHAT') or {}
  if (live.get('id')!=r['post_id'] or live.get('teamId')!=c.team or live.get('status')!='POSTED' or live.get('deletedAt') or snap.get('type','STORY')!='STORY' or snap.get('uploadIds')!=r.get('group_upload_ids',[r['upload_id']])):raise BundleError('source_live_mismatch')

def main():
 c=SavedClient();c.check()
 audit=StateFile('saved-story-audits/daily-20261004.json');report=audit.read() or {'started_at':now(),'results':[],'paid_model_requests':0,'reserve':2}
 store=GitHubStore(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN'])
 # Include publication day and actual Riyadh execution day if the batch crosses midnight.
 ledger=[]
 for day in sorted({'2026-10-04',day_key()}):
  _,row=store.read(day)
  charged=sum(e['charged_micro_usd'] for e in row.get('entries',{}).values()) if row is not None else None
  if charged is not None and charged>3000000:raise BundleError('daily_budget_exceeded')
  ledger.append({'day':day,'ledger_present':row is not None,'recorded_micro_usd':charged})
 report['budget_checks']=ledger;report['missing_ledger_not_zero']=True;audit.save(report)
 print('BUDGET '+json.dumps(ledger),flush=True)
 prepared=[]
 for name in ORDER:
  ap=BASE/(name+'.json');a=json.loads(ap.read_text())
  if datetime.fromisoformat(a['not_before'].replace('Z','+00:00'))>datetime.now(timezone.utc):raise BundleError('archive_not_before')
  source=GitHubJournal(a['identity']).read();identity,title,rows=validate_archive(a,source);check_live(c,rows)
  uploads=[r['upload_id'] for r in rows];found=c.find(identity,title,uploads)
  if len(found)>1:raise BundleError('multiple_existing_saved_stories')
  prepared.append((name,ap,a,identity,title,rows,uploads))
 report['quota_before']=c.ensure_capacity(2);audit.save(report)
 for name,ap,a,identity,title,rows,uploads in prepared:
  j=SavedJournal(identity);prior=j.read()
  try:
   if prior.get('status')!='POSTED':c.ensure_capacity(3)
  except BundleError as e:
   report['held']={'package':name,'reason':str(e),'at':now()};audit.save(report);print('HELD '+json.dumps(report['held']),flush=True);return
  # Recheck validity and live source immediately before the side effect.
  validate_archive(a,GitHubJournal(identity).read());check_live(c,rows)
  result=save_story(c,j,identity,title,uploads)
  confirmed=c.confirm(result['post_id'],title,uploads)
  snap=(confirmed.get('externalData') or {}).get('SNAPCHAT') or {}
  if not snap.get('id') or len(snap.get('mediaIds') or [])!=len(uploads):raise BundleError('saved_story_id_or_media_count_missing')
  result.update(approval=str(ap),package=name,scope='SAVED_STORY_ONLY',source_identity=identity,media_sha256=a['media_sha256']);j.save(result)
  b=StateFile('saved-story-backlog.json');backlog=b.read();entries=backlog.setdefault('packages',[])
  entry=next((x for x in entries if x.get('identity')==identity),None)
  if entry is None:entry={'identity':identity,'path':a['manifest'],'title':title,'approved':True,'card_count':len(rows)};entries.insert(0,entry)
  entry.update(status='POSTED',archive_status='POSTED',saved_story_id=snap['id'],saved_post_id=result['post_id'],saved_title=title,saved_receipt_path='saved-story-receipts/'+identity+'.json',saved_confirmed_at=now(),saved_card_count=len(rows),archive_approval=str(ap))
  backlog['updated_at']=now();b.save(backlog)
  r={'package':name,'title':title,'status':'POSTED','saved_story_id':snap['id'],'post_id':result['post_id'],'reused':prior.get('status')=='POSTED'}
  report['results']=[x for x in report['results'] if x['package']!=name]+[r];audit.save(report);print('SAVED '+json.dumps(r,ensure_ascii=False),flush=True)
 report['quota_after']=c.ensure_capacity(2);report['completed_at']=now();audit.save(report)
 print('COMPLETE '+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
