import base64,json,os
from pathlib import Path
from datetime import datetime,timezone
from publishing_v2.bundle_api import BundleClient,GitHubJournal,load_package,check_predecessors,publish
from publishing_v2.readability import validate_readability,require_for_new_delivery
from daily_budget import GitHubStore,day_key
ORDER=['messi-20261007']
EXPECTED=['18d9594d97bcecfe3069990d0eaadac0b121ef66c8f022bbb21c0667d7a4cc01']
c=BundleClient();c.check();packages=[]
for slug,expected in zip(ORDER,EXPECTED):
 p=Path('approved')/slug/'manifest.json';m=json.loads(p.read_text())
 for f in m['media']:
  path=Path(f['path']);path.write_bytes(base64.b64decode(Path(str(path)+'.b64').read_text(),validate=True))
 now=datetime.now(timezone.utc)
 assert datetime.fromisoformat(m['not_before'])<=now<datetime.fromisoformat(m['expires_at'])
 identity,title,media=load_package(str(p));assert identity==expected and len(media)==2
 validate_readability(p.parent/'readability.json',media)
 j=GitHubJournal(identity);prior=j.read();assert not prior.get('_group')
 require_for_new_delivery(str(p),media,prior)
 packages.append((p,m,identity,title,media,j,prior))
pending=sum(prior.get(str(i),{}).get('status')!='POSTED' for *_,media,j,prior in packages for i in range(1,len(media)+1))
print('QUOTA_BEFORE',json.dumps(c.ensure_capacity(pending+2)),flush=True)
_,ledger=GitHubStore(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN']).read(day_key())
total=None
assert ledger is not None, "cost_ledger_missing"
if ledger is not None:
 total=sum(e.get('charged_micro_usd',0)+(e.get('reserved_micro_usd',0) if e.get('status')!='settled' else 0) for e in ledger.get('entries',{}).values());assert total<=3000000
print('BUDGET',json.dumps({'day':day_key(),'ledger_present':ledger is not None,'total_micro_usd':total,'paid_model_requests':0,'new_paid_generation':False}),flush=True)
confirmed=[]
for p,m,identity,title,media,j,prior in packages:
 check_predecessors(m.get('predecessors',[]))
 # Existing SENDING/post IDs are handled only by the approved publisher.
 publish(c,j,title,media)
 state=j.read()
 for idx in range(1,len(media)+1):
  r=state[str(idx)];live=c.call('/post/'+r['post_id']);snap=live['data']['SNAPCHAT'];ext=live['externalData']['SNAPCHAT']
  assert r['status']=='POSTED' and live['status']=='POSTED' and live['teamId']==c.team and not live.get('deletedAt')
  assert snap['type']=='STORY' and snap['uploadIds']==[r['upload_id']] and snap['storyDuration']=='ONE_WEEK'
  assert ext['status']=='PUBLISHED' and ext['id'] and ext.get('sourceUploadIds')==[r['upload_id']]
  assert ext['id'] not in confirmed;confirmed.append(ext['id'])
  state[str(idx)]['snapchat_id']=ext['id'];state[str(idx)]['verified_duration']='ONE_WEEK';j.save(state)
  print('CONFIRMED',json.dumps({'package':p.parent.name,'post_id':r['post_id'],'snapchat_id':ext['id'],'duration':'ONE_WEEK','identity':identity}),flush=True)
 bj=GitHubJournal(identity);bj.path='/contents/saved-story-backlog.json';backlog=bj.read()
 if not any(row.get('identity')==identity for row in backlog.get('packages',[])):
  backlog.setdefault('packages',[]).insert(0,{'identity':identity,'package':p.parent.name,'title':title,'manifest':str(p),'source_commit':os.environ['APPROVED_COMMIT'],'card_count':2,'status':'PENDING_SAVE_APPROVAL','publication_status':'POSTED','note':'Owner-approved Messi two-card package. Independent archive reconciliation required.'});bj.save(backlog)
print('FINAL_QUOTA',json.dumps(c.ensure_capacity(2)),flush=True)
