"""Free, deterministic Apple correction; publication reuses reviewed bytes."""
import argparse, hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

SOURCE = 'https://www.apple.com/newsroom/2026/08/apple-introduces-new-mac-studio-with-m5-max-and-m5-ultra/'
IMAGE_BASE = 'https://www.apple.com/newsroom/images/2026/08/apple-introduces-new-mac-studio-with-m5-max-and-m5-ultra/article/'
PREDECESSORS = ['356d2118d7a908137474de401838f67183911696fc31d6cef4723c06bcbc283d']
ASSETS = [
 ('hero','4a753142b8d380adbc2b001754102ca580be32750938c6a370cd3cbef0e76a8d'),
 ('Draw-Things','70df8578b78c244280c3d97ec36c00928cfe5927a16da76f2d8a0e26b7dad950'),
 ('LM-Studio-and-MATLAB','35ced0553b7d5b144fcb725d207bd32aa3cabec0b3dc4d462c6834cec068657a'),
 ('rear-ports','80e2e480b0e785073c338586d3984a6121c13d97512618ee2cf723124e06604f'),
]
SPEC = {
 'title':'ليش أبل تبي الذكاء الاصطناعي يشتغل عندك؟',
 'attention':{'source_url':SOURCE,'announced_at':'2026-08-25','event_date':'2026-09-22',
 'event':'بدء توفر Mac Studio','status':'completed','valid_until':'2026-09-27T00:00:00+03:00'},
 'sources':[{'url':SOURCE}],
 'claims':{
 'a1':'Compact desktop supporting large on-device AI models.',
 'a2':'Local model processing can keep requests on-device; this does not cover every app or network request.',
 'a3':'Up to 512GB memory; this configuration is due late October, not September 22.',
 'a4':'Apple reports up to 3x inference speed with four systems in its tests, not every task.'},
 'cards':[
 {'kind':'info','title':'ليش أبل تبي الذكاء الاصطناعي عندك؟',
 'body':'Mac Studio كمبيوتر مكتبي صغير من أبل. الجيل الجديد يقدر يشغّل نماذج ذكاء اصطناعي كبيرة على الجهاز نفسه، بدون ما يرسل كل طلب لسيرفر بعيد.',
 'punch':'الفكرة: جزء أكبر من الشغل يصير عندك.','claim_ids':['a1']},
 {'kind':'story','title':'طلبك يقدر يبقى داخل جهازك',
 'body':'إذا كان النموذج يشتغل بالكامل على جهازك، يقدر يعالج طلبك محليًا. هذا يقلل حاجتك ترسل ملفاتك لسيرفرات خارجية.',
 'punch':'لكن هذا يعتمد على البرنامج وطريقة تشغيله.','claim_ids':['a2']},
 {'kind':'story','title':'حجم صغير… وذاكرة كبيرة',
 'body':'أبل رفعت ذاكرة Mac Studio إلى ٥١٢ غيغابايت، عشان يستوعب نماذج أكبر. هذي النسخة بتتوفر أواخر أكتوبر، بعد بداية طرح الجهاز في سبتمبر.',
 'punch':'مو كل نسخ الجهاز نزلت بنفس الموعد.','claim_ids':['a3']},
 {'kind':'story','title':'أربعة أجهزة تشتغل مع بعض',
 'body':'تقدر تربط أكثر من Mac Studio عبر منافذ Thunderbolt. وبحسب اختبارات أبل، أربعة أجهزة وصلت لسرعة أعلى بثلاث مرات في بعض مهام الذكاء الاصطناعي مقارنة بجهاز واحد.',
 'punch':'الزيادة تختلف حسب المهمة؛ مو وعد لكل استخدام.','claim_ids':['a4'],
 'image_caption':'منافذ الربط في Mac Studio — صورة أبل'}]}
for card,(name,sha) in zip(SPEC['cards'],ASSETS):
 url=IMAGE_BASE+'Apple-Mac-Studio-'+name+'-260825_big.jpg.large.jpg'
 card['image']={'subject':'Mac Studio','provider':'primary_media','source_kind':'official',
 'website_entity':'Q312','official_site':'https://www.apple.com/','source_url':SOURCE,
 'original_url':url,'download_url':url,
 'asset_id':'primary:'+hashlib.sha256((SOURCE+'\n'+url).encode()).hexdigest()[:24],
 'sha256':sha,'credit':'Apple','title':'Mac Studio: '+name,
 'license':'All rights reserved','licensing_verified':False,
 'rights_status':'owner_accepted_editorial_use','owner_use_decision':'owner-source-editorial-use-2026-09-22',
 'image_role':'Official product illustration, not a photograph of a four-system cluster'}

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def validate_spec(spec,now):
 """Bind the manually checked facts and images; not an automated fact checker."""
 if now.tzinfo is None: raise ValueError('timezone_required')
 a=spec['attention'];event=datetime.fromisoformat(a['event_date']).date()
 if (a['source_url']!=SOURCE or a['status']!='completed' or not 0<=(now.date()-event).days<=7
     or now>=datetime.fromisoformat(a['valid_until'])):
  raise ValueError('source_or_current_event_not_validated')
 if len(spec['cards'])!=len(ASSETS):raise ValueError('card_image_count_mismatch')
 seen=set()
 for card,(name,sha) in zip(spec['cards'],ASSETS):
  im=card['image'];url=IMAGE_BASE+'Apple-Mac-Studio-'+name+'-260825_big.jpg.large.jpg'
  if im['subject']!='Mac Studio' or im['sha256']!=sha or im['original_url']!=url or im['source_url']!=SOURCE or sha in seen:
   raise ValueError('wrong_or_repeated_product_image')
  seen.add(sha)
  if not card.get('claim_ids') or any(c not in spec['claims'] for c in card['claim_ids']):raise ValueError('unsupported_card_claim')
  if len(' '.join(card[k] for k in ('title','body','punch')).split())>65:raise ValueError('card_too_dense')

def prepare(output,now):
 validate_spec(SPEC,now)
 from PIL import Image
 from publishing_v2.preview import render_card
 from publishing_v2.autopilot.credits import render_credits
 from publishing_v2.publication import image_publication_eligible
 os.environ['THEME']='light';os.environ['FONT_FAMILY']='Almarai'
 import story_bot
 output.mkdir(parents=True,exist_ok=True);media=[]
 for i,c in enumerate(SPEC['cards']):
  im=c['image'];source=output/f'source-{i}.jpg';target=output/f'card-{i:02d}.jpg'
  if not image_publication_eligible(im):raise ValueError('image_use_not_authorized')
  if not source.exists():
   with urlopen(im['original_url'],timeout=30) as r:source.write_bytes(r.read(10_000_001))
  if hashlib.sha256(source.read_bytes()).hexdigest()!=im['sha256']:raise ValueError('official_source_image_changed')
  if i==0:
   render_card({'title_lines':[c['title']],'body_lines':[c['body']],'closing_lines':[c['punch']],'brand':'ملخص تنفيذي - معلومة'},source,target)
  else:
   counter=f'{i} من {len(SPEC["cards"])-1}'.translate(str.maketrans('0123456789','٠١٢٣٤٥٦٧٨٩'))
   story_bot.render_frame(target.with_suffix('.png'),'ملخص تنفيذي - قصة',counter,c['title'],64,
    sub=c['body'],photo=source,punch=c['punch'],photo_caption=c.get('image_caption'))
   with Image.open(target.with_suffix('.png')) as frame:frame.convert('RGB').save(target,'JPEG',quality=95)
  media.append({'path':str(target),'kind':c['kind'],'image':im,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
 render_credits(SPEC,output/'source-0.jpg',output/'credits-review-only.jpg')
 manifest={'approved':True,'format':'apple-correction-v1','account':'executivesaudi','title':SPEC['title'],'expires_at':SPEC['attention']['valid_until'],
  'media':media,'predecessors':PREDECESSORS,'spec_sha256':digest(SPEC)}
 (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 (output/'spec.json').write_text(json.dumps(SPEC,ensure_ascii=False,indent=2))
 print('Prepared four cards for pixel review. No paid requests; no publishing.')

def validate_review(output):
 manifest=json.loads((output/'manifest.json').read_text());p=output/'visual-review.json'
 if not p.exists():raise ValueError('pixel_review_required')
 review=json.loads(p.read_text())
 required=['source_matches','current_trigger','facts','saudi_language','clear_sequence','readable','images_match','distinct_images','arabic_numbering','brand_preserved']
 if (review.get('manifest_sha256')!=digest(manifest) or manifest.get('spec_sha256')!=digest(SPEC)
     or any(review.get('checks',{}).get(k) is not True for k in required)
     or manifest.get('predecessors')!=PREDECESSORS):raise ValueError('review_missing_or_stale')
 return manifest

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--mode',choices=['preview','publish'],default='preview')
 parser.add_argument('--output',type=Path,default=Path('apple-corrected-preview'))
 args=parser.parse_args();now=datetime.now(timezone.utc)
 if args.mode=='preview':prepare(args.output,now);return
 if os.environ.get('GITHUB_REPOSITORY')!='khalidonline/daily-news-snap' or os.environ.get('GITHUB_REF')!='refs/heads/main':raise ValueError('configured_main_required')
 from publishing_v2.bundle_api import BundleClient,GitHubJournal,check_predecessors,load_package,publish
 validate_spec(SPEC,now);manifest=validate_review(args.output)
 identity,title,media=load_package(args.output/'manifest.json')
 check_predecessors(manifest['predecessors'])
 client=BundleClient();client.check()
 publish(client,GitHubJournal(identity),title,media)

if __name__=='__main__':main()
