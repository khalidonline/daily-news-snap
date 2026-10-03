"""Explicit compact archive replacement; preserves all original receipts and daily posts."""
import importlib.util,json,os,sys
from pathlib import Path
from publishing_v2.bundle_api import BundleError,GitHubJournal
from publishing_v2.saved_story_api import SavedClient,SavedJournal,save_story,now
spec=importlib.util.spec_from_file_location('archive_batch','review/archive-final-20261001/archive_batch.py')
batch=importlib.util.module_from_spec(spec);spec.loader.exec_module(batch)
A=Path('approved/archive-compact-20261003/approval.json')
def main():
 approvals=json.loads(A.read_text())
 files=[batch.validate(a) for a in approvals]
 if '--validate' in sys.argv:
  for a in approvals:
   bad=dict(a,approved=False)
   try:batch.validate(bad)
   except ValueError:pass
   else:raise ValueError('Approval guard failed')
  print('Two editions verified; approval/hash guards active');return
 c=SavedClient();c.check()
 from daily_budget import GitHubStore,day_key
 _,ledger=GitHubStore(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN']).read(day_key())
 if ledger is not None and sum(e['charged_micro_usd'] for e in ledger.get('entries',{}).values())>3000000:raise BundleError('Budget exceeded')
 print('Budget ledger present:',ledger is not None,'; zero paid model calls in archive-only path',flush=True)
 for a in approvals:
  original=GitHubJournal(a['source_identity']).read()
  rows=[{k:original[i].get(k) for k in ['status','post_id','upload_id']} for i in sorted((k for k in original if k.isdigit()),key=int)]
  if rows!=a['source_rows']:raise BundleError('Source receipt changed')
  old=SavedJournal(a['source_identity']).read();bound=a['previous_saved']
  if any(old.get(k)!=bound.get(k) for k in ['identity','post_id','title','upload_ids','status']):raise BundleError('Previous archive mismatch')
  c.confirm(old['post_id'],old['title'],old['upload_ids'])
 pending=sum(SavedJournal(a['identity']).read().get('status')!='POSTED' for a in approvals)
 print(json.dumps({'quota':c.ensure_capacity(pending)}),flush=True)
 for a,media in zip(approvals,files):
  j=SavedJournal(a['identity']);prior=j.read()
  if prior.get('status')=='POSTED':
   c.confirm(prior['post_id'],a['title'],prior['upload_ids']);result=prior
  else:
   mj=batch.MediaJournal(a['identity'])
   uploads=[batch.upload_once(c,mj,a['identity'],i,f) for i,f in enumerate(media)]
   result=save_story(c,j,a['identity'],a['title'],uploads)
  result.update(source_identity=a['source_identity'],package=a['package'],scope='SAVED_STORY_ONLY',authorization=a['authorization'],replaces_saved_post_id=a['previous_saved']['post_id'],old_deletion_status='PENDING_SNAPCHAT_APP')
  j.save(result)
  oldj=SavedJournal(a['source_identity']);old=oldj.read()
  old.update(replacement_identity=a['identity'],replacement_post_id=result['post_id'],replacement_confirmed_at=result['confirmed_at'],old_deletion_status='PENDING_SNAPCHAT_APP')
  oldj.save(old)
  backlog=GitHubJournal(a['source_identity']);backlog.path='/contents/saved-story-backlog.json'
  data=backlog.read()
  for p in data['packages']:
   if p.get('identity')==a['source_identity']:
    p.update(previous_saved_story_id=a['previous_saved']['provider_result']['externalData']['SNAPCHAT']['id'],previous_saved_post_id=a['previous_saved']['post_id'],saved_post_id=result['post_id'],saved_story_id=result['provider_result']['externalData']['SNAPCHAT']['id'],saved_title=a['title'],saved_edition_identity=a['identity'],saved_card_count=2,saved_receipt_path='saved-story-receipts/'+a['identity']+'.json',saved_confirmed_at=result['confirmed_at'],old_deletion_status='PENDING_SNAPCHAT_APP')
  data['updated_at']=now();backlog.save(data)
  print('COMPACT_RESULT '+json.dumps({'title':a['title'],'status':result['status'],'post_id':result['post_id'],'saved_story_id':result['provider_result']['externalData']['SNAPCHAT']['id']}),flush=True)
if __name__=='__main__':main()
