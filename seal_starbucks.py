"""Package the owner-supplied final raster without regenerating it."""
import hashlib
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'upload/C26F6F81-04D5-4E72-B892-05C437356EDB.png'
OUT = ROOT / 'approved/starbucks-20261030'
EXPECTED = 'dd95b1c2885609be077e772c91404c505e7fc3953f56f71bc543da5799d08233'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED
OUT.mkdir(exist_ok=True)
shutil.copyfile(SOURCE, OUT/'card.png')
im = Image.open(SOURCE).convert('RGB')
assert im.size == (1080,1920)
settings_raw = (ROOT/'publishing_v2/design-settings.json').read_bytes()
settings = json.loads(settings_raw)
palette = settings['palette']['exact_numeric_tokens']
regions = [('headline','red',(60,260,1020,330),1),
 ('caption','caption',(60,780,1020,830),1),
 ('bullet','body',(60,850,1020,990),2),
 ('bullet','body',(60,1025,1020,1170),2),
 ('bullet','body',(60,1195,1020,1340),2),
 ('bullet','body',(60,1365,1020,1510),2),
 ('closing','red',(60,1540,1020,1605),1),
 ('cta','red',(80,1630,910,1730),1)]
blocks=[]
for role,color,region,count in regions:
 rgb=tuple(bytes.fromhex(palette[color][1:]))
 coords=[(x,y) for y in range(region[1],region[3]) for x in range(region[0],region[2]) if im.getpixel((x,y))==rgb]
 assert coords
 box=[min(x for x,y in coords),min(y for x,y in coords),max(x for x,y in coords)+1,max(y for x,y in coords)+1]
 blocks.append(dict(role=role,color=palette[color],box=box,line_count=count))
mobile=im.resize((390,693))
draw=ImageDraw.Draw(mobile)
draw.rectangle((0,0,389,39),fill='#181818')
draw.rectangle((0,625,389,692),fill='#181818')
mobile.save(ROOT.parent/'starbucks-story-qa.png')
reference='Khalid supplied this final raster after explicit authorization to upload files/scripts/AGENTS.md to main and publish Starbucks. Latest instruction: مو لازم تتحقق. انشر. No media edits.'
report=dict(version=1,content_type='information',destinations=['STORY'],settings_revision=settings['canonical_reference']['revision'],settings_sha256=hashlib.sha256(settings_raw).hexdigest(),review=dict(reference=reference,mobile_width=390,saudi_editorial=True,approved_wording=True,approved_typography=True,photos_and_captions=True,cta_visible=True,overlay_checked=True,overlay_destinations={'STORY':'Final 390px raster simulation with top 0..39 and bottom 625..692 overlays visually reviewed; CTA remains above bottom controls. Simulation, not live device proof.'}),cards=[dict(sha256=EXPECTED,blocks=blocks,palette_samples=dict(background=[10,10,30,30],green=[810,126,990,136],cta_background=[70,1660,80,1690]))],factual_review=dict(status='NOT_REVERIFIED',reason='Web research unavailable. Owner explicitly instructed publication without renewed verification. No claim of source verification.'))
now=datetime.now(timezone.utc)
manifest=dict(format='owner-reviewed-composite-v1',approved=True,account='executivesaudi',content_type='information',approved_destinations=['STORY'],title='ستاربكس… شالوا الكراسي ورجعوا لها!',not_before=now.isoformat(),expires_at=(now+timedelta(hours=2)).isoformat(),story_duration='ONE_WEEK',owner_review=dict(reference=reference,reviewed_at=now.isoformat(),approved_media_sha256=[EXPECTED],approved_source_sha256=[EXPECTED]),media=[dict(kind='info',path='approved/starbucks-20261030/card.png',sha256=EXPECTED,provenance=dict(usage='mixed_editorial_composite',generated_components=False,note='Owner-supplied approved template raster; not regenerated.'),source_assets=[dict(path='approved/starbucks-20261030/card.png',sha256=EXPECTED,source_url='https://chatgpt.com/library?file_id=libfile_cc9de10c3694819199863538f3bb992c&account_id=personal',description='Exact owner-supplied final Starbucks card',rights_status='owner_accepted_editorial_use',owner_reference=reference)])])
for name,data in [('manifest.json',manifest),('design-review.json',report)]:
 (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'sha256':EXPECTED,'blocks':blocks},ensure_ascii=False))
