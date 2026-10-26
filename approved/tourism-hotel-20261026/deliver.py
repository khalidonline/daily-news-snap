"""Deliver Khalid's exact approved hotel export; never generate media."""
import hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
from daily_budget import GitHubStore,day_key
from publishing_v2.bundle_api import BundleClient,GitHubJournal,load_package,publish
from publishing_v2.readability import require_for_new_delivery

manifest='approved/tourism-hotel-20261026/manifest.json'
identity,title,media=load_package(manifest)
client=BundleClient();client.check()
report=GitHubJournal('hotel-20261026-preflight')
_,ledger=GitHubStore(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN']).read(day_key())
budget={'day':day_key(),'limit_usd':3,'new_paid_model_requests':0,'mode':'delivery_of_existing_media_only'}
if ledger is None:
    budget['status']='UNKNOWN_MISSING_LEDGER_NOT_ZERO'
else:
    budget['charged_micro_usd']=sum(e['charged_micro_usd'] for e in ledger['entries'].values())
    budget['status']='READ_CURRENT_LEDGER'
    if budget['charged_micro_usd']>3000000:raise RuntimeError('Daily budget exceeded')
report.save({'checked_at':datetime.now(timezone.utc).isoformat(),'video_sha256':hashlib.sha256(media[0][1]).hexdigest(),'budget':budget,'owner_authorization':'انشر after final v2 preview','destinations':['STORY','SPOTLIGHT']})
for destination in ['STORY','SPOTLIGHT']:
    key=identity if destination=='STORY' else hashlib.sha256((identity+':SPOTLIGHT').encode()).hexdigest()
    journal=GitHubJournal(key);existing=journal.read()
    require_for_new_delivery(manifest,media,existing)
    quota=client.ensure_capacity(3 if destination=='SPOTLIGHT' else 4)
    state=report.read();state['quota_'+destination]=quota;report.save(state)
    publish(client,journal,title,media,placement=destination)
    receipt=journal.read();row=receipt['1']
    if row['status']!='POSTED':raise RuntimeError('Publication not confirmed')
    remote=client.call('/post/'+row['post_id'])
    if remote.get('status')!='POSTED':raise RuntimeError('Provider status not POSTED')
    state=report.read();state[destination]={'status':'POSTED','post_id':row['post_id'],'externalData':remote.get('externalData',{}),'media_sha256':hashlib.sha256(media[0][1]).hexdigest()};report.save(state)
    print(json.dumps({destination:state[destination]},ensure_ascii=False))
