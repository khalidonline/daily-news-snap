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
trump={'path':str(p/'trump.jpg'),'sha256':sha(p/'trump.jpg'),'source_url':'https://commons.wikimedia.org/wiki/File:January_2025_Official_Presidential_Portrait_of_Donald_J._Trump.jpg','description':'January 2025 inaugural portrait by Daniel Torok; resized to 700px width.','rights_status':'public_domain','credit':'Daniel Torok','rights_basis':'Author public domain dedication, documented on Commons.','original_sha256':sha(Path('/workspace/scratch/6eccb5ef02c0/trump-original.jpg'))}
m['media'][0]['source_assets']=[asset,trump]
m['owner_review']={'reference':'Khalid requested adding Trump beside Capitol and publishing. Revised export undergoing preparation.','approved_media_sha256':[sha(p/'card.png')],'approved_source_sha256':[asset['sha256'],trump['sha256']]}
save('manifest.json',m)
a=read(old/'archive-approval.json')
from publishing_v2.information_request import identity
a.update(approved=False,manifest=str(p/'manifest.json'),manifest_sha256=sha(p/'manifest.json'),identity=identity(m),title=copy['headline'],expires_at=m['expires_at'],owner_authorization='Awaiting hash-bound authorization staging for requested revision.')
save('archive-approval.json',a)
save('sources.json',{'facts':['https://www.axios.com/2026/11/03/election-day-midterm-trump-democrats-republicans','https://www.abc.net.au/news/2026-11-04/democrats-claim-victory-over-republicans-2026-midterm-elections/107338138'],'as_of_riyadh':'2026-11-04T09:35:39+03:00','image_assets':[asset,trump],'image_treatment':'Capitol dome detail left; full Trump portrait contained without distortion right. Archival photographs, not election-day photos.','status':'Revised draft pending hash-bound authorization'})
r=read(old/'design-review.json')
r['settings_sha256']=sha(Path('publishing_v2/design-settings.json'))
r['cards'][0].update(sha256=sha(p/'card.png'),blocks=read(p/'blocks.json'))
r['review']['reference']='Inspected both final 390x693 Story and Saved Story simulations: Capitol dome left, Trump right with respective captions. Four two-line bullets; title and closing one line; CTA visible. Exact approved copy preserved. Overlay simulation, not live device measurement.'
save('design-review.json',r)
