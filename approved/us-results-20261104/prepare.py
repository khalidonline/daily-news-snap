import json, hashlib
from pathlib import Path
p=Path('approved/us-results-20261104')
old=Path('approved/us-midterms-20261101')
def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,value): (p/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
copy=read(p/'copy.json')
m=read(old/'manifest.json')
m.update(approved=False,title=copy['headline'],not_before='2026-11-04T00:00:00+00:00',expires_at='2026-11-05T20:59:59+00:00')
m['media'][0].update(path=str(p/'card.png'),sha256=sha(p/'card.png'))
asset=read(old/'sources.json')['image_assets'][0]
m['media'][0]['source_assets']=[asset]
m['owner_review']={'reference':'Design requested after measured shortened draft. Final export not yet approved for publication.','approved_media_sha256':[sha(p/'card.png')],'approved_source_sha256':[asset['sha256']]}
save('manifest.json',m)
a=read(old/'archive-approval.json')
a.update(approved=False,manifest=str(p/'manifest.json'),manifest_sha256=sha(p/'manifest.json'),identity=sha(p/'card.png'),title=copy['headline'],expires_at=m['expires_at'],owner_authorization='Not authorized; design preview only.')
save('archive-approval.json',a)
save('sources.json',{'facts':['https://www.axios.com/2026/11/03/election-day-midterm-trump-democrats-republicans','https://www.abc.net.au/news/2026-11-04/democrats-claim-victory-over-republicans-2026-midterm-elections/107338138'],'as_of_riyadh':'2026-11-04T09:35:39+03:00','image_assets':[asset],'image_treatment':'Upper panorama crop retaining full Capitol dome; archival 2011 photo, not election-day photo.','status':'Draft; no publication authorization'})
r=read(old/'design-review.json')
r['settings_sha256']=sha(Path('publishing_v2/design-settings.json'))
r['cards'][0].update(sha256=sha(p/'card.png'),blocks=read(p/'blocks.json'))
r['review']['reference']='Inspected both final 390x693 Story and Saved Story simulations after upper crop correction. Full dome visible. Four two-line bullets, title/closing one line, CTA visible above lower simulated overlay. Actual device appearance not claimed. Exact measured shortened text retained.'
save('design-review.json',r)
