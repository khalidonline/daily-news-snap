from pathlib import Path
import json, hashlib, shutil
from datetime import datetime, timezone
from PIL import Image, ImageDraw

root=Path.cwd()
src=root/'drafts/oxford-fixed-template'
out=root/'approved/oxford-20261027'
out.mkdir(exist_ok=True)
shutil.copyfile(src/'Oxford-Template-Preview.png',out/'card.png')
shutil.copyfile(src/'source-approved.png',out/'source-approved.png')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cardsha=sha(out/'card.png'); sourcesha=sha(out/'source-approved.png')
now=datetime.now(timezone.utc).isoformat()
reference='Khalid approved the displayed Oxford-Template-Preview.png version 4 and said انشر, then كمل for packaging and delivery; no image bytes changed.'
manifest={'format':'owner-reviewed-composite-v1','approved':True,'account':'executivesaudi',
 'content_type':'information','approved_destinations':['STORY'],
 'title':'أكسفورد للمشاة… مو ليوم واحد!','not_before':now,'expires_at':'2026-10-27T20:59:59+00:00',
 'story_duration':'ONE_WEEK','owner_review':{'reference':reference,'reviewed_at':now,
 'approved_media_sha256':[cardsha],'approved_source_sha256':[sourcesha]},
 'media':[{'kind':'info','path':'approved/oxford-20261027/card.png','sha256':cardsha,
 'provenance':{'usage':'mixed_editorial_composite','generated_components':False,
 'note':'Deterministic text template; photographic panels retained from owner-approved source composite. Historical original-image provenance is not established by this manifest.'},
 'source_assets':[{'path':'approved/oxford-20261027/source-approved.png','sha256':sourcesha,
 'source_url':'https://chatgpt.com/library?file_id=libfile_ac4862226ee48191a0f42f8af9ae98ff&account_id=personal',
 'description':'Previously approved Oxford composite used only as photo-panel and sharing-arrow source',
 'rights_status':'owner_accepted_editorial_use','owner_reference':'Khalid selected the street picture and approved the final two-picture Oxford card; this is not a copyright license.'}]}]}
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
report=json.loads((src/'review.json').read_text())
settings=root/'publishing_v2/design-settings.json'
review={'version':1,'content_type':'information','destinations':['STORY'],
 'settings_revision':json.loads(settings.read_text())['canonical_reference']['revision'],
 'settings_sha256':sha(settings),'review':{'reference':reference,'mobile_width':390,
 'saudi_editorial':True,'approved_wording':True,'regular_font':False,'approved_typography':True,
 'photos_and_captions':True,'cta_visible':True,'overlay_checked':False,
 'overlay_destinations':{}},'cards':[{'sha256':cardsha,'blocks':report['blocks'],
 'palette_samples':{'background':[10,10,30,30],'green':[810,126,990,136],'cta_background':[70,1660,80,1690]}}]}
(out/'design-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
Image.open(out/'card.png').resize((390,693)).save(src/'mobile-review.png')
overlay=Image.open(src/'mobile-review.png').convert('RGB')
draw=ImageDraw.Draw(overlay)
draw.rectangle((0,0,389,39),fill='#222222')
draw.rectangle((0,625,389,692),fill='#222222')
draw.text((10,12),'Story header UI (simulation)',fill='white')
draw.text((10,650),'Reply / reactions UI (simulation)',fill='white')
overlay.save(src/'story-overlay-review.png')
print(json.dumps({'prepared':str(out),'sha256':cardsha,'published':False}))
