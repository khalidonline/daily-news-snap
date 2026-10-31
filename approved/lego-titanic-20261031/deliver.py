"""Deliver Khalid's exact approved cafes export; never generate media."""
import hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
from daily_budget import GitHubStore,day_key
from publishing_v2.bundle_api import BundleClient,GitHubJournal,load_package,publish
from publishing_v2.readability import require_for_new_delivery

manifest='approved/lego-titanic-20261031/manifest.json'
identity,title,media=load_package(manifest)
client=BundleClient();client.check()
report=GitHubJournal('lego-titanic-20261031-preflight')
budget={'day':day_key(),'limit_usd':3,'new_paid_model_requests':0,'mode':'existing_media_delivery_only','total_daily_spend':'NOT_ASSERTED','cost_ledger_not_a_posting_prerequisite':True}
report.save({'checked_at':datetime.now(timezone.utc).isoformat(),'video_sha256':hashlib.sha256(media[0][1]).hexdigest(),'budget':budget,'owner_authorization':'Owner approved 25-topic batch and two daily slots; B1 LEGO Titanic reference price','destinations':['STORY','SPOTLIGHT']})
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
    if remote.get('status')!='POSTED' or remote.get('externalData',{}).get('SNAPCHAT',{}).get('status')!='PUBLISHED':raise RuntimeError('Provider status not POSTED')
    state=report.read();state[destination]={'status':'POSTED','post_id':row['post_id'],'externalData':remote.get('externalData',{}),'media_sha256':hashlib.sha256(media[0][1]).hexdigest()};report.save(state)
    print(json.dumps({destination:state[destination]},ensure_ascii=False))
