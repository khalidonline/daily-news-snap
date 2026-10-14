from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageOps
ROOT=Path.cwd()
prefix=(ROOT/'drafts/nvidia-sega-20261007/render.py').read_text().split('DATA=[')[0]
exec(prefix)
OUT=ROOT/'drafts/messi-20261007'
DATA=[{'title':'اليوم ميسي ودّع… وبدايته كانت طرد!', 'photo':'messi-archive.jpg','caption':'ميسي بقميص الأرجنتين — صورة أرشيفية','bullets':['فجر اليوم ٧ أكتوبر، ختم مشواره مع الأرجنتين بهدف وصناعة هدفين أمام بنين.','أول مباراة له عام ٢٠٠٥ انتهت بطرده بعد ثواني من دخوله.','أنهى مشواره بـ٢٠٨ مباريات و١٢٦ هدف.'],'closing':['لكن قبل هالوداع بـ١٠ سنوات…','كان قرر يترك المنتخب.']},{'title':'اعتزل من القهر… ورجع بطل العالم','photo':'worldcup.jpg','caption':'ميسي يرفع كأس العالم في قطر — ٢٠٢٢','bullets':['في ٢٠١٦، ضيّع ركلة ترجيح وخسر نهائي كوبا أمريكا، وأعلن اعتزاله الدولي.','رجع للمنتخب؛ وفاز بكوبا أمريكا في ٢٠٢١، ثم كأس العالم في ٢٠٢٢.','وفي ٢٠٢٤، أضاف لقب كوبا أمريكا الثاني.'],'closing':['لو وقف عند خسارة ٢٠١٦…','كان فوّت أهم بطولاته مع المنتخب.']}]
records=[]
for i,c in enumerate(DATA):
 im=base(c['title'],('١','٢')[i]);d=ImageDraw.Draw(im)
 # Taller photo area preserves trophy and face together.
 y0,y1=425,1010
 photo=ImageOps.fit(Image.open(OUT/c['photo']).convert('RGB'),(916,y1-y0),method=Image.Resampling.LANCZOS,centering=(.5,.45))
 mask=Image.new('L',photo.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,y1-y0-1),30,fill=255);im.paste(photo,(82,y0),mask)
 text(im,c['caption'],990,y1+14,27,MUTED)
 y=1080;bs=[]
 for copy in c['bullets']:
  lines=['']
  for w in copy.split():
   trial=(lines[-1]+' '+w).strip()
   if d.textlength(trial,font=font(48),direction='rtl')>875:lines.append(w)
   else:lines[-1]=trial
  assert len(lines)<=2,(copy,lines)
  d.ellipse((983,y+17,996,y+30),fill=GREEN)
  for k,line in enumerate(lines):text(im,line,965,y+64*k,48)
  bs.append({'text':copy,'font_px':48,'lines':lines});y+=len(lines)*64+12
 assert y<=1510,y
 for j,line in enumerate(c['closing']):text(im,line,992,1510+j*59,46,RED,True)
 footer(im);badge(im,512,1800,56)
 save(im,i)
 records.append({'headline':{'text':c['title'],'font_px':53,'lines':1},'bullets':bs})
(OUT/'copy.json').write_text(json.dumps({'status':'DESIGN_REVIEW_ONLY_NOT_APPROVED_FOR_PUBLICATION','cards':DATA,'layout':records,'sources':['https://www.reuters.com/sports/soccer/messi-signs-off-tears-after-one-last-argentina-master-class-2026-10-07/','https://www.aljazeera.net/sport/2026/10/7/ميسي-يودع-منتخب-الأرجنتين'],'photos':['https://www.ligaolahraga.com/bola/hadapi-benin-di-buenos-aires-argentina-siapkan-perpisahan-untuk-lionel-messi','https://www.gzeromedia.com/what-were-watching-argentine-soccer-ecstasy-chinese-covid-cover-up-brits-on-strike']},ensure_ascii=False,indent=2))
print('Rendered two 1080x1920 cards; body 48px; headlines 53px single line; no publication.')
