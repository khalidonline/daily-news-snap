from PIL import Image,ImageDraw,ImageFont,ImageOps
from pathlib import Path
import json,hashlib
P=Path(__file__).parent
font=lambda n,b=False:ImageFont.truetype('fonts/Almarai-'+('Bold' if b else 'Regular')+'.ttf',n)
navy='#15394e';green='#174b38';red='#aa263a';bg='#eeeae2'
rows=[[('السعودية','١٩٪',19),('مصر','١٨٪',18),('الجزائر','١٣٪',13),('إيران','١٢٪',12),('باكستان','٦٪',6)],[('السعودية','١٧٫٢٪',17.2),('تونس','١٣٫٧٪',13.7),('إسرائيل','١١٫٩٪',11.9),('الإمارات','١٠٫١٪',10.1),('إيران','٧٫٥٪',7.5)]]
titles=[['إنتاج السعودية من التمور'],['مين يصدّر تمور أكثر؟']]
copy=[]
for i in range(2):
 im=Image.new('RGB',(1080,1920),bg);d=ImageDraw.Draw(im)
 def text(x,y,s,size=52,b=False,c=navy):
  assert d.textlength(s,font=font(size,b),direction='rtl')<=920,(s,size)
  d.text((x,y),s,font=font(size,b),fill=c,anchor='rt',direction='rtl',language='ar')
 def badge(x,y,n):
  b=Image.open('images/brand/badge.png').convert('RGB').resize((n,n));m=Image.new('L',(n,n));ImageDraw.Draw(m).ellipse((0,0,n-1,n-1),fill=255);im.paste(b,(x,y),m)
 badge(82,155,94);d.rectangle((876,169,990,179),fill=green)
 text(990,200,'ملخص تنفيذي · معلومة',30,True,green);text(990,249,['١ من ٢','٢ من ٢'][i],28,c='#827e77')
 for j,t in enumerate(titles[i]):text(990,305+j*74,t,59,True,red)
 photo_y=410
 ph=ImageOps.fit(Image.open(Path('approved/dates-20261004')/f'photo-{i}.jpg').convert('RGB'),(916,330));mask=Image.new('L',ph.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,ph.height-1),radius=28,fill=255);im.paste(ph,(82,photo_y),mask)
 text(990,764,['سوق تمور العلا — صورة أرشيفية','تمر سكري من القصيم — صورة أرشيفية'][i],25,c='#817d75')
 if i==0:
  label='حصة السعودية وأبرز الدول من إنتاج التمور في ٢٠٢٤';y=1020
 else:
  text(990,875,'صادرات التمور عالميًا: ٢٫٦٣ مليار دولار (٢٠٢٤)',41)
  label='وهذي حصة أبرز الدول من قيمة الصادرات';y=1110
 text(990,y-85,label,39,True,green)
 for j,(country,pct,v) in enumerate(rows[i]):
  yy=y+j*(106 if i==0 else 88)
  text(990,yy,country,52,j==0,green if j==0 else navy)
  d.rounded_rectangle((210,yy+14,700,yy+42),radius=8,fill='#dad6ce')
  w=round(490*v/20);d.rounded_rectangle((700-w,yy+14,700,yy+42),radius=8,fill=green if j==0 else '#93a8a0')
  text(190,yy,pct,50,True,green if j==0 else navy)
 if i==0:
  text(990,1590,'السعودية تنتج قرابة خُمس تمور العالم.',47,True,red)
 else:
  text(990,1590,'قيمة صادرات تونس أكثر من ٣ أضعاف مصر.',43,True,red)
  d.rounded_rectangle((82,1715,998,1815),radius=26,fill='#efdee0')
  text(868,1740,'شاركها مع صديقك اللي يحب التمر',36,True,red)
  d.line([(913,1780),(918,1755),(933,1742),(951,1740),(951,1725),(975,1748),(951,1772),(951,1757),(934,1760),(913,1780)],fill=red,width=5,joint='curve')
 badge(510,1836,60)
 im.save(P/f'card-{i:02}.jpg',quality=95,subsampling=0);im.resize((432,768)).save(P/f'preview-{i}.png')
 copy.append({'title':titles[i],'rows':rows[i]})
(P/'copy.json').write_text(json.dumps({'cards':copy,'production_conclusion':'السعودية تنتج قرابة خُمس تمور العالم.','export_intro':'صادرات التمور عالميًا: ٢٫٦٣ مليار دولار (٢٠٢٤)','owner_changes':'فصل الإنتاج عن التصدير؛ حذف فقط؛ العناوين والتمهيد بسطر واحد','owner_removed':'المفاجأة'},ensure_ascii=False,indent=2))
