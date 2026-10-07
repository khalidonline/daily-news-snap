import base64,json,os,hashlib
from pathlib import Path
from datetime import datetime,timezone
from publishing_v2.bundle_api import BundleClient,GitHubJournal,load_package,publish
from publishing_v2.readability import validate_readability,require_for_new_delivery
from daily_budget import GitHubStore,day_key
CONTENT='8b1b68757f92e05c919afeac533214ec3dce70e7b2e2dcb36796a3ff6a59f972'
FIRST='258a09d54c9221c3d44723c6cd9a0b0dd0f1c7997d6ad62c58a7fad0a5789a2d'
ORIGINAL='5e63a9e4f8edc7d3e71de8575429d6e46380cc2efc5a42ca992c74614010d6bc'
DELIVERY='owner-reorder-20261007-133300-'+CONTENT
# Separate explicitly authorized repeat delivery; media identity and bytes remain unchanged.
approval=json.loads(Path('approved/nvidia-order-repair-20261007/authorization.json').read_text())
assert approval['approved'] is True and approval['content_identity']==CONTENT and approval['delivery_key']==DELIVERY
now=datetime.now(timezone.utc)
assert datetime.fromisoformat(approval['not_before'])<=now<datetime.fromisoformat(approval['expires_at'])
p=Path('approved/nvidia-card2-corrected-20261007/manifest.json')
m=json.loads(p.read_text())
for row in m['media']:
 path=Path(row['path']);path.write_bytes(base64.b64decode(Path(str(path)+'.b64').read_text(),validate=True))
identity,title,media=load_package(str(p));assert identity==CONTENT and len(media)==1
validate_readability(p.parent/'readability.json',media)
c=BundleClient();c.check()
first=GitHubJournal(FIRST).read();prior=GitHubJournal(CONTENT).read()
assert first['1']['status']=='POSTED' and first['1']['post_id']=='4017285a-1b22-448b-9478-7919c7474dae'
assert prior['1']['status']=='POSTED' and prior['1']['post_id']=='4623a58d-8194-422b-8f3d-ebcab0d43fa0'
f=c.call('/post/'+first['1']['post_id'])
assert f['status']=='POSTED' and f['teamId']==c.team and not f.get('deletedAt') and f['externalData']['SNAPCHAT']['status']=='PUBLISHED'
j=GitHubJournal(DELIVERY);state=j.read()
if state:
 assert state.get('authorization')==approval, 'Delivery scope changed'
else:
 state['authorization']=approval;j.save(state)
require_for_new_delivery(str(p),media,state)
print('QUOTA_BEFORE',json.dumps(c.ensure_capacity(2+(0 if state.get('1',{}).get('status')=='POSTED' else 1))),flush=True)
_,ledger=GitHubStore(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN']).read(day_key())
total=None
if ledger is not None:
 total=sum(e.get('charged_micro_usd',0)+(e.get('reserved_micro_usd',0) if e.get('status')!='settled' else 0) for e in ledger.get('entries',{}).values());assert total<=3000000
print('BUDGET',json.dumps({'day':day_key(),'ledger_present':ledger is not None,'total_micro_usd':total,'paid_model_requests':0}),flush=True)
publish(c,j,title,media)
state=j.read();r=state['1'];live=c.call('/post/'+r['post_id']);snap=live['data']['SNAPCHAT'];ext=live['externalData']['SNAPCHAT']
assert r['status']=='POSTED' and live['status']=='POSTED' and live['teamId']==c.team and not live.get('deletedAt')
assert snap['type']=='STORY' and snap['uploadIds']==[r['upload_id']] and snap['storyDuration']=='ONE_WEEK'
assert ext['status']=='PUBLISHED' and ext['id'] and ext.get('sourceUploadIds')==[r['upload_id']]
assert ext['id'] not in [first['1']['snapchat_id'],prior['1']['snapchat_id']]
assert datetime.fromisoformat(live['postDate'].replace('Z','+00:00'))>datetime.fromisoformat(f['postDate'].replace('Z','+00:00'))
state['1'].update(snapchat_id=ext['id'],verified_duration='ONE_WEEK',content_identity=CONTENT,ordered_after_post_id=first['1']['post_id']);j.save(state)
oldj=GitHubJournal(CONTENT);old=oldj.read();old['1']['superseded_by_delivery']={'receipt_key':DELIVERY,'post_id':r['post_id']};old['1']['deletion_status']='OWNER_HANDLES_NOT_CONFIRMED';oldj.save(old)
bj=GitHubJournal(DELIVERY);bj.path='/contents/saved-story-backlog.json';backlog=bj.read()
for row in backlog.get('packages',[]):
 if row.get('identity')==ORIGINAL:
  row.update(status='PENDING_FINAL_COMPOSITION_REVIEW',delivery_card_sources=[{'identity':FIRST,'card':1},{'identity':CONTENT,'receipt_key':DELIVERY,'card':1}],note='Final order: SEGA-logo first card then explicitly re-delivered corrected RIVA second card. Both POSTED; do not archive older deliveries. Owner handles old deletions; not confirmed.')
bj.save(backlog)
print('CONFIRMED',json.dumps({'post_id':r['post_id'],'snapchat_id':ext['id'],'duration':'ONE_WEEK','receipt_key':DELIVERY,'ordered_after':first['1']['post_id']}),flush=True)
print('FINAL_QUOTA',json.dumps(c.ensure_capacity(2)),flush=True)
