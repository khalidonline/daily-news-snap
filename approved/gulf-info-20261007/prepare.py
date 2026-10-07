from pathlib import Path
import json,hashlib
from publishing_v2.primary_images import identity
items=[('gulf-info-20261007','photo.png','https://ajel.sa/sports/tyyrjrp56','https://cdn.ajel.sa/articles/2026-10/Capture-crop-bOIx_dWv.png'),('gulf-challenge-20261007','crest.png','https://en.wikipedia.org/wiki/File:Saudi_Arabia_national_football_team_logo.svg','https://thumb.wikimedia.org/wikipedia/en/thumb/e/ee/Saudi_Arabia_national_football_team_logo.svg/500px-Saudi_Arabia_national_football_team_logo.svg.png')]
for slug,asset,source,url in items:
 p=Path('approved')/slug;copy=json.loads((p/'copy.json').read_text());h=hashlib.sha256((p/'card-00.jpg').read_bytes()).hexdigest()
 image={'provider':'primary_media','source_kind':'article','source_url':source,'original_url':url,'download_url':url,'asset_id':identity(source,url),'owner_use_decision':'owner-source-editorial-use-2026-09-22','rights_status':'owner_accepted_editorial_use','license':'All rights reserved','licensing_verified':False,'sha256':hashlib.sha256((p/asset).read_bytes()).hexdigest()}
 m={'approved':True,'account':'executivesaudi','title':copy['headline'],'not_before':'2026-10-07T06:39:09Z','expires_at':'2026-10-07T20:59:59Z','story_duration':'ONE_WEEK','approval':'Khalid 2026-10-07 09:39:09 Riyadh explicitly requested changing the closing to return to titles and publishing with the previously proposed team-logo challenge. Uses existing compact identity, reviewed originals and one card each. No sources/answer published. Closing uses the last-title year 2004 to avoid inconsistent elapsed-year claims.','media':[{'kind':'info','path':str(p/'card-00.jpg'),'sha256':h,'image':image}]}
 (p/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
 review={'reviewed':True,'scope':'one-card information' if 'info' in slug else 'exact 4x4 visual challenge','mobile_preview':'540x960 inspected; headline single line; large body; no overlap; established brand','source_asset':image,'internal_sources':['https://ajel.sa/sports/tyyrjrp56','https://www.okaz.com.sa/sport/na/2269656','https://agcff.com/1532/','https://www.national-football-teams.com/country/139/2009/Oman.html'],'statistical_wording':'All confrontations won counts advancement on penalties; not an official all-wins regulation-time statistical claim. Kuwait 1974 no conceded goals; Oman 2009 drawn group game excluded.','answer_internal_only':copy.get('answer_internal_only'),'paid_model_calls':0,'identity':hashlib.sha256(('executivesaudi:'+h).encode()).hexdigest()}
 (p/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
 info='info' in slug
 headline_size=copy.get('headline_font',52)
 if not info:
  from PIL import Image,ImageDraw,ImageFont
  d=ImageDraw.Draw(Image.new('RGB',(1,1)))
  while d.textlength(copy['headline'],font=ImageFont.truetype('fonts/Almarai-Bold.ttf',headline_size),direction='rtl')>916:headline_size-=1
 blocks=[{'text':'\n'.join(lines),'size':48,'box':[90,y,956,y+144]} for lines,y in zip(copy.get('bullets',[]),[1015,1197])] if info else [{'text':copy['prompt'],'size':51,'box':[82,406,992,478]}]
 cy=1550 if info else 1600
 readability={'version':1,'visual_review':{'approved':True,'reference':'Assistant actual 540x960 mobile preview inspection 2026-10-07; large type, distinct photo/grid and no overlap; Khalid authorized publication 09:39 Riyadh.'},'cards':[{'sha256':h,'headline':{'text':copy['headline'],'size':headline_size,'box':[82,305,992,378]},'bullets':blocks,'cta':{'text':'شاركها مع صديقك اللي تعجبه هذي المعلومة','size':38,'box':[82,cy+13,878,cy+119]}}]}
 (p/'readability.json').write_text(json.dumps(readability,ensure_ascii=False,indent=2));print(slug,review['identity'])
