import base64,json,os
from pathlib import Path
from datetime import datetime,timezone
from publishing_v2.bundle_api import BundleClient,GitHubJournal,load_package,check_predecessors,publish
from daily_budget import GitHubStore,day_key
p='approved/instagram-20261006/manifest.json'
m=json.loads(Path(p).read_text())
for f in m['media']:
 path=Path(f['path']);path.write_bytes(base64.b64decode(Path(str(path)+'.b64').read_text(),validate=True))
now=datetime.now(timezone.utc)
assert datetime.fromisoformat(m['not_before'].replace('Z','+00:00'))<=now<datetime.fromisoformat(m['expires_at'].replace('Z','+00:00'))
identity,title,media=load_package(p)
assert identity=='fd063efb445c6d527c14a1f8e6d2aa206e16282f8abe4a9b634d94356020ea08' and len(media)==1
c=BundleClient();c.check();j=GitHubJournal(identity);prior=j.read()
assert not prior.get('_group')
pending=int('1' not in prior)
print('QUOTA',json.dumps(c.ensure_capacity(pending+2)),flush=True)
_,ledger=GitHubStore(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN']).read(day_key())
total=None
if ledger is not None:
 total=sum(e.get('charged_micro_usd',0)+(e.get('reserved_micro_usd',0) if e.get('status')!='settled' else 0) for e in ledger.get('entries',{}).values())
 assert total<=3000000
print('BUDGET',json.dumps({'day':day_key(),'ledger_present':ledger is not None,'total_micro_usd':total,'paid_model_requests':0}),flush=True)
check_predecessors(m.get('predecessors',[]))
try:
 publish(c,j,title,media)
except Exception:
 state=j.read();row=state.get('1',{})
 if row.get('post_id'):
  live=c.call('/post/'+row['post_id']);external=(live.get('externalData') or {}).get('SNAPCHAT') or {}
  print('PENDING_DETAIL',json.dumps({'post_id':row['post_id'],'status':live.get('status'),'snapchat_status':external.get('status'),'snapchat_id':external.get('id')}),flush=True)
 raise
state=j.read();r=state['1'];live=c.call('/post/'+r['post_id']);snap=live['data']['SNAPCHAT'];ext=live['externalData']['SNAPCHAT']
assert r['status']=='POSTED' and live['status']=='POSTED' and live['teamId']==c.team and not live.get('deletedAt')
assert snap['type']=='STORY' and snap['uploadIds']==[r['upload_id']] and snap['storyDuration']=='ONE_WEEK' and ext['status']=='PUBLISHED' and ext['id']
state['1']['snapchat_id']=ext['id'];state['1']['verified_duration']='ONE_WEEK';j.save(state)
print('CONFIRMED',json.dumps({'card':1,'post_id':r['post_id'],'snapchat_id':ext['id'],'duration':snap['storyDuration'],'identity':identity}),flush=True)
bj=GitHubJournal(identity);bj.path='/contents/saved-story-backlog.json';backlog=bj.read()
if not any(row.get('identity')==identity for row in backlog.get('packages',[])):
 backlog.setdefault('packages',[]).insert(0,{'identity':identity,'package':'instagram-20261006','title':title,'manifest':p,'source_commit':os.environ['APPROVED_COMMIT'],'card_count':1,'status':'PENDING_SAVE_APPROVAL','publication_status':'POSTED','note':'Final owner-approved one-card edition; independent archive reconciliation required.'})
 bj.save(backlog)
print('FINAL_QUOTA',json.dumps(c.ensure_capacity(2)),flush=True)
