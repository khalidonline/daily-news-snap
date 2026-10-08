from pathlib import Path
import json,hashlib,base64
p=Path('approved/interest-20261008'); h=lambda b:hashlib.sha256(b).hexdigest()
urls=[('https://commons.wikimedia.org/wiki/File:Eccles_Building_(26088200676).jpg','https://upload.wikimedia.org/wikipedia/commons/8/89/Eccles_Building_%2826088200676%29.jpg','eccles.jpg'),('https://commons.wikimedia.org/wiki/File:President_Ronald_Reagan_and_Paul_Volcker.jpg','https://upload.wikimedia.org/wikipedia/commons/e/e2/President_Ronald_Reagan_Paul_Volcker_Meeting_to_Discuss_Monetary_Policy_with_Paul_Volker_in_Oval_Office_-_DPLA_-_e04117f4897610a724c267cdf855ce73.jpg','volcker.jpg')]
media=[]
for i,(source,url,asset) in enumerate(urls):
 media.append({'kind':'info' if i==0 else 'story','path':str(p/f'card-{i:02}.jpg'),'sha256':h((p/f'card-{i:02}.jpg').read_bytes()),'image':{'provider':'commons','source_url':source,'original_url':url,'asset_id':source,'sha256':h((p/asset).read_bytes()),'license':'Public domain','attribution_required':False,'licensing_verified':True}})
identity=h(('executivesaudi:'+':'.join(x['sha256'] for x in media)).encode())
m={'approved':True,'account':'executivesaudi','title':'ليش يرفعون الفائدة إذا غلت الأسعار؟','not_before':'2026-10-08T08:36:04Z','expires_at':'2026-10-08T20:59:59Z','story_duration':'ONE_WEEK','approval':'Khalid explicitly approved the clarified car-loan explanation and instructed publication on 2026-10-08 at 11:36:04 Riyadh. Two-card layout preserves approved example, causal explanation, 1980/1983 comparison and economic tradeoff at readable 48px type. Postal package not included.','media':media}
(p/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
r=json.loads((p/'readability.json').read_text());r['visual_review']={'approved':True,'reference':'Assistant inspected both actual 540x960 JPG previews 2026-10-08: single-line headlines, 48px two-line bullets, correct distinct archival images, no overlap, no source credits published. Established Almarai template and approved solid CTA arrow.'};(p/'readability.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
(p/'review.json').write_text(json.dumps({'identity':identity,'approved_by_user_at':'2026-10-08T11:36:04+03:00','sources_internal':['https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm','https://www.federalreserve.gov/monetarypolicy/fomcminutes20260916.htm','https://www.federalreservehistory.org/essays/anti-inflation-measures','https://www.bankofengland.co.uk/explainers/how-do-higher-interest-rates-help-to-lower-inflation.'],'review':'Current rate range is central-bank target, not retail loan APR. Historical 20% is federal funds rate peak. Reduced inflation means slower price increases. No claim of immediate effect or sole causality. Image 2 is accurately captioned 1981 archival meeting.','paid_model_requests':0,'paid_image_requests':0},ensure_ascii=False,indent=2))
s=Path('approved/gulf-info-20261007/publish-approved.py').read_text()
a=s.index('ORDER='); b=s.index('c=BundleClient()',a)
s=s[:a]+f'ORDER=["interest-20261008"]\nEXPECTED=["{identity}"]\n'+s[b:]
s=s.replace('and len(media)==1','and len(media)==2').replace("pending=sum(p[-1].get('1',{}).get('status')!='POSTED' for p in packages)","pending=sum(sum(prior.get(str(i+1),{}).get('status')!='POSTED' for i in range(len(media))) for p,m,identity,title,media,j,prior in packages)")
a=s.index(" state=j.read();r=state['1'];")
b=s.index(" bj=GitHubJournal",a)
old=s[a:b]
old=old.replace(" state=j.read();r=state['1'];", "state=j.read();r=state[str(index)];").replace(" state['1']", " state[str(index)]")
s=s[:a]+" for index in range(1,len(media)+1):\n"+'\n'.join(' '+line if line.startswith(' ') else '  '+line for line in old.splitlines())+'\n'+s[b:]
s=s.replace("state['1']['verified_duration']","state[str(index)]['verified_duration']")
s=s.replace("'card_count':1", "'card_count':len(media)").replace('compact one-card edition','compact two-card edition')
(p/'publish-approved.py').write_text(s)
print(identity)
