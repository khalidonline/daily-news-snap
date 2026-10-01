"""Owner-approved archive editions. No daily posting, generation, or old receipt mutation."""
import base64,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
from publishing_v2.bundle_api import GitHubJournal,BundleError
from publishing_v2.saved_story_api import SavedClient,SavedJournal,save_story,now

def identity(media):return hashlib.sha256(('executivesaudi:'+':'.join(m['sha256'] for m in media)).encode()).hexdigest()
def validate(a):
 if a.get('approved') is not True or a.get('account')!='executivesaudi' or a.get('scope')!='SAVED_STORY_ONLY' or not a.get('authorization'):raise ValueError('archive_approval_required')
 if 'national' in a['package'].lower() or 'اليوم الوطني' in a['title']:raise ValueError('owner_excluded_national_day')
 if datetime.fromisoformat(a['expires_at'].replace('Z','+00:00'))<=datetime.now(timezone.utc):raise ValueError('archive_approval_expired')
 rows=a.get('source_rows',[])
 if not rows or any(r.get('status')!='POSTED' or not r.get('post_id') or not r.get('upload_id') for r in rows):raise ValueError('source_not_posted')
 media=a.get('media',[])
 if not 1<=len(media)<=10 or identity(media)!=a.get('identity') or len({m['sha256'] for m in media})!=len(media):raise ValueError('archive_identity_mismatch')
 result=[]
 for m in media:
  if m.get('kind') not in ['info','story','topic']:raise ValueError('nonpublic_card')
  p=Path(m['path'])
  if '..' in p.parts or p.suffix.lower() not in ['.jpg','.jpeg','.png']:raise ValueError('invalid_media_path')
  b=p.read_bytes() if p.exists() else base64.b64decode(Path(str(p)+'.b64').read_bytes())
  if hashlib.sha256(b).hexdigest()!=m['sha256']:raise ValueError('media_changed')
  result.append((p,b))
 return result

class MediaJournal(GitHubJournal):
 def __init__(self,source):
  super().__init__(source);self.path='/contents/saved-story-media/'+source+'.json'

def upload_once(client,journal,edition,index,media):
 state=journal.read()
 if state and state.get('identity')!=edition:raise BundleError('upload_edition_changed')
 state=state or {'identity':edition,'cards':{}}
 key=str(index);prior=state['cards'].get(key)
 if prior:
  if prior['sha256']!=hashlib.sha256(media[1]).hexdigest():raise BundleError('upload_hash_changed')
  if not prior.get('upload_id'):raise BundleError('ambiguous_upload_no_retry')
  return prior['upload_id']
 prior={'status':'UPLOADING','intent_at':now(),'sha256':hashlib.sha256(media[1]).hexdigest()};state['cards'][key]=prior;journal.save(state)
 prior['upload_id']=client.upload(media);prior['status']='UPLOADED';journal.save(state)
 return prior['upload_id']

def preflight(c,a):
 source=GitHubJournal(a['source_identity']).read()
 actual=[source[k] for k in sorted((k for k in source if k.isdigit()),key=int)]
 if [{k:r.get(k) for k in ['status','post_id','upload_id']} for r in actual]!=a['source_rows']:raise BundleError('source_receipts_changed')
 journal=SavedJournal(a['source_identity']);state=journal.read()
 if state:
  if state.get('identity')!=a['identity']:raise BundleError('other_saved_edition_exists')
  return
 for r in a['source_rows']:
  if r['post_id'] in a.get('owner_replaced_post_ids',[]):continue
  live=c.call('/post/'+r['post_id']);snap=(live.get('data') or {}).get('SNAPCHAT') or {}
  if live.get('status')!='POSTED' or live.get('teamId')!=c.team or live.get('deletedAt') or snap.get('type','STORY')!='STORY' or snap.get('uploadIds')!=[r['upload_id']]:raise BundleError('source_live_mismatch')
 # Detect provider autosave or a separately-created archive of the old edition.
 if c.find(a['source_identity'],a['title'],[r['upload_id'] for r in a['source_rows']]):raise BundleError('source_already_archived_needs_reconciliation')
 for alias in a.get('source_title_aliases',[]):
  if alias!=a['title'] and c.find(a['source_identity'],alias,[r['upload_id'] for r in a['source_rows']]):raise BundleError('archive_alias_exists')


def main(path):
 approvals=json.loads(Path(path).read_text())
 if len({a['source_identity'] for a in approvals})!=len(approvals):raise BundleError('duplicate_sources')
 media=[validate(a) for a in approvals] # All editions ready before first upload/save.
 for a in approvals:
  for m in a['media']:
   if Path(m['path']).is_absolute():raise BundleError('absolute_media_path')
  if a.get('owner_replaced_post_ids') and (a['package']!='nespresso-20261001' or a.get('replacement_sha256')!='5ba6ada5f9fd7ebd0f1bd43fcb84826c4ee5b55a82ef349a9373173faacc06ca' or a['media'][-1]['sha256']!=a['replacement_sha256']):raise BundleError('invalid_owner_replacement')
 c=SavedClient();c.check()
 from daily_budget import GitHubStore,day_key
 store=GitHubStore(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN']);_,ledger=store.read(day_key())
 charged=sum(e['charged_micro_usd'] for e in (ledger or {}).get('entries',{}).values())
 if charged>3000000:raise BundleError('daily_budget_exceeded')
 print(json.dumps({'budget_day':day_key(),'recorded_micro_usd':charged,'paid_model_requests':0}),flush=True)
 for a in approvals:preflight(c,a)
 pending=sum(SavedJournal(a['source_identity']).read().get('status')!='POSTED' for a in approvals)
 print(json.dumps({'quota':c.ensure_capacity(pending)}),flush=True)
 for a,files in zip(approvals,media):
  j=SavedJournal(a['source_identity']);prior=j.read()
  if prior.get('status')=='POSTED':
   c.confirm(prior['post_id'],a['title'],prior['upload_ids']);print(json.dumps({'package':a['package'],'status':'POSTED','id':prior['post_id'],'reused':True}),flush=True);continue
  uploads=[];mj=MediaJournal(a['source_identity'])
  for i,(m,f) in enumerate(zip(a['media'],files)):
   reused=m.get('reuse_upload_id')
   if reused:
    if not any(r['upload_id']==reused for r in a['source_rows']):raise BundleError('reuse_not_in_source')
    uploads.append(reused)
   else:uploads.append(upload_once(c,mj,a['identity'],i,f))
  result=save_story(c,j,a['identity'],a['title'],uploads)
  # Canonical source journal blocks a second archive of any former edition.
  result.update(source_identity=a['source_identity'],package=a['package'],authorization=a['authorization'],scope='SAVED_STORY_ONLY',media_sha256=[m['sha256'] for m in a['media']]);j.save(result)
  print('ARCHIVE_RESULT '+json.dumps({'package':a['package'],'status':result['status'],'id':result['post_id'],'provider':result.get('provider_result')}),flush=True)
if __name__=='__main__':main(sys.argv[1])
