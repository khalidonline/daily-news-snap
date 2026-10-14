from pathlib import Path
import json,base64,hashlib
from PIL import Image,ImageDraw,ImageOps
ROOT=Path.cwd(); OUT=ROOT/'approved/interest-20261008'
exec((ROOT/'drafts/nvidia-sega-20261007/render.py').read_text().split('DATA=[')[0])
OUT=ROOT/'approved/interest-20261008'
DATA=[{'title':'ليش يرفعون الفائدة إذا غلت الأسعار؟','photo':'eccles.jpg','caption':'مبنى الفيدرالي الأمريكي — صورة أرشيفية','bullets':[
'أمس نُشر محضر الفيدرالي عن قرارات الفائدة.\nالفائدة الأمريكية اليوم بين ٣٫٧٥٪ و٤٪.',
'ناوي تشتري سيارة بقرض؟ إذا ارتفعت الفائدة،\nتزيد تكلفة قرضك ويمكن تأجل الشراء.',
'وإذا كثير أجّلوا مشترياتهم ومشاريعهم،\nيخف الطلب، وتصعب زيادة الأسعار.'],
'closing':['طيب… وش صار لما وصلت الفائدة ٢٠٪؟']},
{'title':'فائدة ٢٠٪… هدّت الغلا وأتعبت السوق','photo':'volcker.jpg','caption':'بول فولكر مع الرئيس ريغان — ١٩٨١','bullets':[
'في ١٩٨٠، وصلت الفائدة الأمريكية إلى ٢٠٪.\nعلشان يخف الطلب ويهدأ ارتفاع الأسعار.',
'وبحلول ١٩٨٣، تراجع التضخم إلى ٣٫٧٪؛\nيعني الأسعار صارت ترتفع بسرعة أقل.',
'لكن مع تباطؤ الاقتصاد، تضررت الأعمال\nوارتفعت البطالة.'],'closing':['الفائدة العالية تهدّي الغلا…','لكنها تثقّل القروض وتبطّئ السوق.']}]
records=[]
for i,c in enumerate(DATA):
 im=base(c['title'],('١','٢')[i]);d=ImageDraw.Draw(im)
 photo=ImageOps.fit(Image.open(OUT/c['photo']).convert('RGB'),(916,510),method=Image.Resampling.LANCZOS,centering=(.5,.45))
 mask=Image.new('L',photo.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,509),30,fill=255);im.paste(photo,(82,430),mask)
 text(im,c['caption'],992,953,27,MUTED)
 bs=[]
 for j,s in enumerate(c['bullets']):
  y=1020+j*161
  d.ellipse((983,y+17,996,y+30),fill=GREEN)
  for k,line in enumerate(s.split('\n')):text(im,line,965,y+k*65,48)
  bs.append({'text':s,'size':48,'box':[82,y,965,y+130]})
 for j,line in enumerate(c['closing']):text(im,line,992,1521+j*60,46,RED,True)
 footer(im);badge(im,512,1790,56);save(im,i)
 records.append({'sha256':hashlib.sha256((OUT/f'card-{i:02}.jpg').read_bytes()).hexdigest(),'headline':{'text':c['title'],'size':53,'box':[82,320,998,396]},'bullets':bs,'cta':{'text':'شاركها مع صديقك اللي تعجبه هذي المعلومة','size':38,'box':[82,1654,865,1760]}})
(OUT/'copy.json').write_text(json.dumps(DATA,ensure_ascii=False,indent=2))
(OUT/'readability.json').write_text(json.dumps({'version':1,'visual_review':{'approved':False,'reference':'Pending actual mobile inspection'},'cards':records},ensure_ascii=False,indent=2))
print('Rendered two cards; pending visual review')
