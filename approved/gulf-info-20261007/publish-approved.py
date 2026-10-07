import base64,json,os
from pathlib import Path
from datetime import datetime,timezone
from publishing_v2.bundle_api import BundleClient,GitHubJournal,load_package,check_predecessors,publish
from publishing_v2.readability import validate_readability,require_for_new_delivery
from daily_budget import GitHubStore,day_key
ORDER=['gulf-info-20261007','gulf-challenge-20261007']
EXPECTED=['c881699c35fef7ca86d011276d4c5ecac134a47e668cfe499f85f6cd382f94af','8d5dc76c64a0bc7d37553c8f9ebfb03893749ce5d380445bd08d31efc74f8c51']
c=BundleClient();c.check();packages=[]
for slug,expected in zip(ORDER,EXPECTED):
 p=Path('approved')/slug/'manifest.json';m=json.loads(p.read_text())
 for f in m['media']:
  path=Path(f['path']);path.write_bytes(base64.b64decode(Path(str(path)+'.b64').read_text(),validate=True))
 now=datetime.now(timezone.utc)
 assert datetime.fromisoformat(m['not_before'])<=now<datetime.fromisoformat(m['expires_at'])
 identity,title,media=load_package(str(p));assert identity==expected and len(media)==1
 validate_readability(p.parent/'readability.json',media)
 j=GitHubJournal(identity);prior=j.read();assert not prior.get('_group')
 require_for_new_delivery(str(p),media,prior)
 packages.append((p,m,identity,title,media,j,prior))
pending=sum(p[-1].get('1',{}).get('status')!='POSTED' for p in packages)
print('QUOTA_BEFORE',json.dumps(c.ensure_capacity(pending+2)),flush=True)
_,ledger=GitHubStore(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN']).read(day_key())
total=None
if ledger is not None:
 total=sum(e.get('charged_micro_usd',0)+(e.get('reserved_micro_usd',0) if e.get('status')!='settled' else 0) for e in ledger.get('entries',{}).values());assert total<=3000000
print('BUDGET',json.dumps({'day':day_key(),'ledger_present':ledger is not None,'total_micro_usd':total,'paid_model_requests':0,'new_paid_generation':False}),flush=True)
confirmed=[]
for p,m,identity,title,media,j,prior in packages:
 check_predecessors(m.get('predecessors',[]))
 # Existing SENDING/post IDs are handled only by the approved publisher.
 publish(c,j,title,media)
 state=j.read();r=state['1'];live=c.call('/post/'+r['post_id']);snap=live['data']['SNAPCHAT'];ext=live['externalData']['SNAPCHAT']
 assert r['status']=='POSTED' and live['status']=='POSTED' and live['teamId']==c.team and not live.get('deletedAt')
 assert snap['type']=='STORY' and snap['uploadIds']==[r['upload_id']] and snap['storyDuration']=='ONE_WEEK'
 assert ext['status']=='PUBLISHED' and ext['id'] and ext.get('sourceUploadIds')==[r['upload_id']]
 assert ext['id'] not in confirmed;confirmed.append(ext['id'])
 state['1']['snapchat_id']=ext['id'];state['1']['verified_duration']='ONE_WEEK';j.save(state)
 print('CONFIRMED',json.dumps({'package':p.parent.name,'post_id':r['post_id'],'snapchat_id':ext['id'],'duration':'ONE_WEEK','identity':identity}),flush=True)
 bj=GitHubJournal(identity);bj.path='/contents/saved-story-backlog.json';backlog=bj.read()
 if not any(row.get('identity')==identity for row in backlog.get('packages',[])):
  backlog.setdefault('packages',[]).insert(0,{'identity':identity,'package':p.parent.name,'title':title,'manifest':str(p),'source_commit':os.environ['APPROVED_COMMIT'],'card_count':1,'status':'PENDING_SAVE_APPROVAL','publication_status':'POSTED','note':'Owner-approved compact one-card edition. Independent archive reconciliation required.'});bj.save(backlog)
print('FINAL_QUOTA',json.dumps(c.ensure_capacity(2)),flush=True)
