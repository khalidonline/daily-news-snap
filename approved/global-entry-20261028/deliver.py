"""Deliver this exact owner-approved information card through shared gates."""
import json,hashlib
from datetime import datetime,timezone
from publishing_v2.bundle_api import BundleClient,GitHubJournal,load_package,publish
from publishing_v2.readability import require_for_new_delivery
manifest='approved/global-entry-20261028/manifest.json'
identity,title,media=load_package(manifest)
client=BundleClient();client.check()
journal=GitHubJournal(identity)
require_for_new_delivery(manifest,media,journal.read())
quota=client.ensure_capacity(3)
report=GitHubJournal('global-entry-20261028-preflight')
report.save({'checked_at':datetime.now(timezone.utc).isoformat(),'identity':identity,'media_sha256':hashlib.sha256(media[0][1]).hexdigest(),'quota_STORY':quota,'new_paid_model_requests':0,'total_daily_spend':'NOT_ASSERTED','owner_authorization':'عدل العنوان إلى: سالفة المسافر الموثوق في امريكا باختصار. ثم كمل النشر','destinations':['STORY']})
publish(client,journal,title,media,placement='STORY')
row=journal.read()['1']
if row['status']!='POSTED':raise RuntimeError('Publication not confirmed')
remote=client.call('/post/'+row['post_id'])
if remote.get('status')!='POSTED' or remote.get('externalData',{}).get('SNAPCHAT',{}).get('status')!='PUBLISHED':raise RuntimeError('Remote publication not confirmed')
state=report.read();state['STORY']={'status':'POSTED','post_id':row['post_id'],'externalData':remote.get('externalData',{})};report.save(state)
print(json.dumps(state,ensure_ascii=False))
