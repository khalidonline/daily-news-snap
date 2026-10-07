import base64,json,os
from pathlib import Path
from datetime import datetime,timezone
from publishing_v2.bundle_api import BundleClient,GitHubJournal,load_package,check_predecessors,publish
from publishing_v2.readability import validate_readability,require_for_new_delivery
from daily_budget import GitHubStore,day_key
ORDER=['nvidia-card1-sega-20261007']
EXPECTED=['258a09d54c9221c3d44723c6cd9a0b0dd0f1c7997d6ad62c58a7fad0a5789a2d']
c=BundleClient();c.check();packages=[]
original=GitHubJournal('5e63a9e4f8edc7d3e71de8575429d6e46380cc2efc5a42ca992c74614010d6bc').read()
assert original.get('1',{}).get('status')=='POSTED' and original['1'].get('post_id')=='50eff36f-abb1-43ff-b4ac-b292017f1a86'
replacement=original['1'].get('superseded_by')
assert not replacement or replacement.get('identity')=='258a09d54c9221c3d44723c6cd9a0b0dd0f1c7997d6ad62c58a7fad0a5789a2d', 'Different replacement already exists'

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
pending=sum(prior.get(str(i),{}).get('status')!='POSTED' for *_,media,j,prior in packages for i in range(1,len(media)+1))
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
 state=j.read()
 for idx in range(1,len(media)+1):
  r=state[str(idx)];live=c.call('/post/'+r['post_id']);snap=live['data']['SNAPCHAT'];ext=live['externalData']['SNAPCHAT']
  assert r['status']=='POSTED' and live['status']=='POSTED' and live['teamId']==c.team and not live.get('deletedAt')
  assert snap['type']=='STORY' and snap['uploadIds']==[r['upload_id']] and snap['storyDuration']=='ONE_WEEK'
  assert ext['status']=='PUBLISHED' and ext['id'] and ext.get('sourceUploadIds')==[r['upload_id']]
  assert ext['id'] not in confirmed;confirmed.append(ext['id'])
  state[str(idx)]['snapchat_id']=ext['id'];state[str(idx)]['verified_duration']='ONE_WEEK';j.save(state)
  print('CONFIRMED',json.dumps({'package':p.parent.name,'post_id':r['post_id'],'snapchat_id':ext['id'],'duration':'ONE_WEEK','identity':identity}),flush=True)


 oldj=GitHubJournal('5e63a9e4f8edc7d3e71de8575429d6e46380cc2efc5a42ca992c74614010d6bc');oldstate=oldj.read()
 oldstate['1']['superseded_by']={'identity':identity,'card':1,'post_id':state['1']['post_id'],'snapchat_id':state['1']['snapchat_id']}
 oldstate['1']['deletion_status']='NOT_CONFIRMED';oldj.save(oldstate)
 second=GitHubJournal('8b1b68757f92e05c919afeac533214ec3dce70e7b2e2dcb36796a3ff6a59f972').read();assert second['1']['status']=='POSTED'
 bj=GitHubJournal(identity);bj.path='/contents/saved-story-backlog.json';backlog=bj.read()
 for row in backlog.get('packages',[]):
  if row.get('identity')=='5e63a9e4f8edc7d3e71de8575429d6e46380cc2efc5a42ca992c74614010d6bc':
   row.update(status='PENDING_FINAL_COMPOSITION_REVIEW',publication_status='POSTED_WITH_BOTH_CARDS_REPLACED',
    superseded_card_indices=[1,2],latest_revision_identity=identity,
    delivery_card_sources=[{'identity':identity,'card':1},{'identity':'8b1b68757f92e05c919afeac533214ec3dce70e7b2e2dcb36796a3ff6a59f972','card':1}],
    first_revision_manifest=str(p),first_revision_commit=os.environ['APPROVED_COMMIT'],
    note='Final ordered NVIDIA package is SEGA-logo card1 plus public-domain RIVA card2. Never archive original cards. Old-card deletion not confirmed; do not claim it. Reconcile final composition before saving.')
 bj.save(backlog)
print('FINAL_QUOTA',json.dumps(c.ensure_capacity(2)),flush=True)
