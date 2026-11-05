"""Record reviewed draft, never authorize or publish."""
import json, hashlib
from pathlib import Path
from publishing_v2.information_request import identity

p=Path('approved/bonfire-night-20261105')
def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,value): (p/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
copy=read(p/'copy.json')
assets=[
 {'path':str(p/'bonfire.jpg'),'sha256':sha(p/'bonfire.jpg'),
  'source_url':'https://commons.wikimedia.org/wiki/File:131102-F-HA826-936_(10741284974).jpg',
  'description':'Bonfire Night fireworks, Abbey Gardens, Bury St Edmunds, 2 November 2013. Not London and not 2026.',
  'credit':'Dillon Johnston / U.S. Air Force','rights_status':'public_domain',
  'rights_basis':'Official U.S. military photograph; Commons PD-USGov-Military. Thumbnail downloaded at 960px.'},
 {'path':str(p/'parliament.jpg'),'sha256':sha(p/'parliament.jpg'),
  'source_url':'https://www.parliament.uk/globalassets/house-of-commons/hoc-digital/news-story-images/palace-exterior/palace-of-westminster-2022.jpg',
  'description':'Present Palace of Westminster and Elizabeth Tower from the Thames. Official exterior image, filename 2022. Not the 1605 building.',
  'credit':'UK Parliament','rights_status':'not_verified',
  'rights_basis':'Public official website source; no open-license claim. Reference retained internally per owner policy.'}
]
m={'format':'owner-reviewed-composite-v1','approved':False,'account':'executivesaudi',
   'content_type':'information','approved_destinations':['STORY','SAVED_STORY'],
   'title':copy['headline'],'not_before':'2026-11-05T00:00:00+03:00',
   'expires_at':'2026-11-05T23:59:59+03:00','story_duration':'ONE_WEEK',
   'owner_review':{'reference':'Khalid approved shortened exact copy with تمام and requested design with كمل. Export awaits preview and publication approval.',
    'approved_media_sha256':[sha(p/'card.png')],'approved_source_sha256':[a['sha256'] for a in assets]},
   'media':[{'kind':'info','path':str(p/'card.png'),'sha256':sha(p/'card.png'),
     'provenance':{'usage':'mixed_editorial_composite','generated_components':False},'source_assets':assets}]}
save('manifest.json',m)
save('archive-approval.json',{'approved':False,'account':'executivesaudi',
 'manifest':str(p/'manifest.json'),'manifest_sha256':sha(p/'manifest.json'),
 'identity':identity(m),'public_indices':[1],'title':m['title'],'expires_at':m['expires_at'],
 'owner_authorization':'Not authorized; awaiting review of uploaded export.',
 'empty_profile_confirmation':'Existing profile has previous stories; check current provider inventory and overlap before any create; not an empty-profile assertion.'})
save('sources.json',{'facts':['https://www.parliament.uk/about/faqs/house-of-commons-faqs/gunpowder-plot/','https://www.gov.uk/government/news/government-backs-great-british-tradition-of-bonfire-night'],
 'as_of_riyadh':'2026-11-05','image_assets':assets,
 'image_treatment':'Two real archival photos. Fireworks left captioned as 2013; current Parliament right. Normal panel cropping only, no fabricated celebration at Parliament.',
 'excluded_candidate':'Huck Lewes 2023 image download returned 403; not used.',
 'status':'DRAFT_NOT_AUTHORIZED'})
settings=read(Path('publishing_v2/design-settings.json'))
review={'version':1,'content_type':'information','settings_revision':settings['canonical_reference']['revision'],
 'settings_sha256':sha(Path('publishing_v2/design-settings.json')),'status':'DESIGN_REVIEWED_NOT_AUTHORIZED',
 'cards':[{'sha256':sha(p/'card.png'),'blocks':read(p/'blocks.json'),
  'palette_samples':{'background':[10,10,30,30],'green':[935,142,1005,144],'cta_background':[70,1680,80,1710]}}],
 'destinations':['STORY','SAVED_STORY'],
 'review':{'reference':'Inspected full 1080x1920 export and both 390x693 overlay simulations. Real fireworks left, Palace and Big Ben right, correct individual captions. Approved exact copy; four two-line points; single title and closing; CTA visible. No live-device claim.',
  'mobile_width':390,'saudi_editorial':True,'approved_wording':True,'approved_typography':True,
  'photos_and_captions':True,'cta_visible':True,'overlay_checked':True,
  'overlay_destinations':{'STORY':'Inspected top0..39/bottom625..692 masked simulation; all essential text and CTA visible.',
  'SAVED_STORY':'Inspected separate same-player masked simulation; essential text and CTA visible.'}}}
save('design-review.json',review)
