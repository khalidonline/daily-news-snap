from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,subprocess
R=Path('.');P=R/'approved/lego-titanic-20261031';O=R/'approved/dunkin-starbucks-20261031'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((O/n).read_text().replace('dunkin-starbucks-20261031','lego-titanic-20261031'))
def put(n,d):(P/n).write_text(json.dumps(d,ensure_ascii=False,indent=2))
now=datetime.now(timezone.utc);expiry=(now+timedelta(days=2)).isoformat();title='توقع السعر — ليغو تايتانيك'
ref='Khalid approved B1 and delegated production/publication. Agent reviewed eight decoded states and separate modeled390px Story/Spotlight overlays. Approved audio PCM compared unchanged; no subjective listening or owner viewing claimed.'
m=read('manifest.json');m.update(title=title,expires_at=expiry);v=sha(P/'challenge.mp4');m['media'][0]['sha256']=v;m['challenge_contract']['final_video_review'].update(sha256=v,reference=ref);m['video_review'].update(authorization=ref,video_sha256=v)
g=json.loads((P/'geometry.json').read_text());frames=[];designs=[]
for t in [.5,3.5,4.5,5.5,6.5,7.5,8.5,11.5]:
 n=f'frame-{t}.png';f=dict(at=t,path=str(P.relative_to(R)/n),sha256=sha(P/n));frames.append(f);designs.append(dict(at=t,sha256=f['sha256'],blocks=g[str(t)],palette_samples={'background':[60,1120,80,1140],'green':[850,126,870,136],'cta_background':[100,1670,120,1690]}))
m['video_review']['frames']=frames
s=read('source-approval.json');s.update(title=title,expires_at=expiry);s['media'][0]['sha256']=sha(P/'source.png')
urls=['https://www.lego.com/cdn/cs/set/assets/blte957e68c74be55ab/10294_alt25.jpg','https://www.lego.com/cdn/cs/set/assets/bltb7509d53386b49d5/10294_alt36.jpg'];assets=[]
for n,u in zip(['full.jpg','build.jpg'],urls):assets.append(dict(path=str(P.relative_to(R)/n),sha256=sha(P/n),source_url=u,rights_status='owner_accepted_editorial_use',description='Real official LEGO Titanic10294 product photograph; delegated editorial use, no blanket license claim.',owner_reference='Khalid approved B1 and delegated real-photo selection, production and publication.'))
s['media'][0]['source_assets']=assets;s['owner_review']=dict(reference=ref,reviewed_at=now.isoformat(),approved_media_sha256=[sha(P/'source.png')],approved_source_sha256=[a['sha256'] for a in assets]);put('source-approval.json',s)
m['video_review']['source_manifest']['sha256']=sha(P/'source-approval.json');put('manifest.json',m)
d=read('design-review.json');d.update(settings_revision=json.loads((R/'publishing_v2/design-settings.json').read_text())['canonical_reference']['revision'],settings_sha256=sha(R/'publishing_v2/design-settings.json'));d['review']['reference']=ref;d['cards']=[dict(sha256=v,frame_designs=designs)];put('design-review.json',d)
def pcm(p):return subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-map','0:a:0','-f','s16le','-ar','48000','-ac','1','-'])
a=pcm(P/'challenge.mp4');b=pcm(R/'approved/wheels-video-20261025/owner-approved-audio.m4a');assert a==b
put('production-evidence.json',dict(pcm_equal=True,pcm_sha256=hashlib.sha256(a).hexdigest(),video_sha256=v,subjective_listening=False,new_paid_model_requests=0,total_daily_spend='UNKNOWN'))
put('sources.json',dict(checked_date='2026-10-31',url='https://www.lego.com/en-us/product/lego-titanic-10294',price_usd=679.99,conversion_reference=3.75,rounded_sar=2550,price_label='US reference price, not current Saudi retail price',photos=urls))
s=(O/'deliver.py').read_text().replace('dunkin-starbucks-20261031','lego-titanic-20261031').replace('A1 Dunkin versus Starbucks','B1 LEGO Titanic reference price');(P/'deliver.py').write_text(s)
w=(R/'.github/workflows/deliver-dunkin-starbucks-approved.yml').read_text().replace('Dunkin Starbucks','LEGO Titanic').replace('dunkin-starbucks','lego-titanic').replace('cat approved/lego-titanic-20261031.tar.xz.part-* | tar -xJf -','tar -xJf approved/lego-titanic-20261031.tar.xz');(R/'.github/workflows/deliver-lego-titanic-approved.yml').write_text(w)
print(v)
