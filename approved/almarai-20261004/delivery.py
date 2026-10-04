"""One approved package, no paid generation; executed only in Actions."""
import base64,json,sys
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from publishing_v2.bundle_api import BundleClient,GitHubJournal,HTTPFailure,load_package,publish,check_predecessors
manifest='approved/almarai-20261004/manifest.json'
data=json.loads(Path(manifest).read_text())
now=datetime.now(timezone.utc)
assert datetime.fromisoformat(data['not_before'].replace('Z','+00:00'))<=now<datetime.fromisoformat(data['expires_at'].replace('Z','+00:00'))
identity,title,media=load_package(manifest)
assert identity=='8d2e337c276980974d4570ac95c47d9d350b906783123ba235b07d532cfdd6e3'
check_predecessors(data['predecessors'])
j=GitHubJournal(identity);state=j.read()
assert '_group' not in state
c=BundleClient();c.check()
required=sum(str(i+1) not in state for i in range(len(media)))
usage=c.ensure_capacity(required+2)
print('QUOTA_BEFORE',json.dumps(usage['posts']))
day=now.astimezone(ZoneInfo('Asia/Riyadh')).date().isoformat()
try:
 ledger=j.call('/contents/daily/'+day+'.json?ref=cost-ledger')
 ledger=json.loads(base64.b64decode(ledger['content']))
 entries=ledger.get('entries',[])
 if isinstance(entries,dict):entries=list(entries.values())
 spent=sum(int(e.get('charged_micro_usd',0))+(int(e.get('reserved_micro_usd',0)) if e.get('status')!='settled' else 0) for e in entries)
 assert spent<=3_000_000, 'Daily project cap reached'
 print('COST_LEDGER_MICRO_USD',spent)
except HTTPFailure as e:
 if e.code!=404:raise
 print('COST_LEDGER_UNKNOWN: missing daily ledger, not zero; this delivery makes no paid model calls')
publish(c,j,title,media)
state=j.read();ids=[];posts=[]
for n in ('1','2'):
 r=state[n];assert r['status']=='POSTED'
 row=c.call('/post/'+r['post_id']);s=row.get('data',{}).get('SNAPCHAT',{});e=row.get('externalData',{}).get('SNAPCHAT',{})
 assert row['teamId']==c.team and row['status']=='POSTED' and not row.get('deletedAt')
 assert s['type']=='STORY' and s['storyDuration']=='ONE_WEEK' and s['uploadIds']==[r['upload_id']]
 assert e['status']=='PUBLISHED' and e['sourceUploadIds']==[r['upload_id']] and len(e['mediaIds'])==1
 ids+=e['mediaIds'];posts.append(r['post_id']);r['media_id']=e['mediaIds'][0];r['confirmed_at']=datetime.now(timezone.utc).isoformat()
assert len(set(ids))==2 and len(set(posts))==2
j.save(state)
print('VERIFIED_POSTED',json.dumps({'identity':identity,'post_ids':posts,'media_ids':ids,'duration':'ONE_WEEK'}))
print('QUOTA_AFTER',json.dumps(c.ensure_capacity(2)['posts']))
