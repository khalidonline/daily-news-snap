from PIL import Image,ImageDraw,ImageFont,ImageOps
from pathlib import Path
import json,hashlib
P=Path(__file__).parent
font=lambda n,b=False:ImageFont.truetype('fonts/Almarai-'+('Bold' if b else 'Regular')+'.ttf',n)
navy='#15394e';green='#174b38';red='#aa263a';bg='#eeeae2'
rows=[[('السعودية','١٩٪',19),('مصر','١٨٪',18),('الجزائر','١٣٪',13),('إيران','١٢٪',12),('باكستان','٦٪',6)],[('السعودية','١٧٫٢٪',17.2),('تونس','١٣٫٧٪',13.7),('إسرائيل','١١٫٩٪',11.9),('الإمارات','١٠٫١٪',10.1),('إيران','٧٫٥٪',7.5)]]
titles=[['أمس أُعلنت صدارة تمورنا…','كم ننتج من تمر العالم؟'],['مين يبيع تمر','للعالم أكثر؟']]
copy=[]
for i in range(2):
 im=Image.new('RGB',(1080,1920),bg);d=ImageDraw.Draw(im)
 def text(x,y,s,size=52,b=False,c=navy):
  assert d.textlength(s,font=font(size,b),direction='rtl')<=920,(s,size)
  d.text((x,y),s,font=font(size,b),fill=c,anchor='rt',direction='rtl',language='ar')
 def badge(x,y,n):
  b=Image.open('images/brand/badge.png').convert('RGB').resize((n,n));m=Image.new('L',(n,n));ImageDraw.Draw(m).ellipse((0,0,n-1,n-1),fill=255);im.paste(b,(x,y),m)
 badge(82,126,128);d.rectangle((858,156,990,166),fill=green)
 text(990,196,'ملخص تنفيذي · معلومة',30,True,green);text(990,261,['١ من ٢','٢ من ٢'][i],28,c='#827e77')
 for j,t in enumerate(titles[i]):text(990,330+j*85,t,59,True,red)
 ph=ImageOps.fit(Image.open(P/f'photo-{i}.jpg').convert('RGB'),(916,290));mask=Image.new('L',ph.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,289),radius=28,fill=255);im.paste(ph,(82,515),mask)
 text(990,823,['سوق تمور العلا — صورة أرشيفية','تمر سكري من القصيم — صورة أرشيفية'][i],25,c='#817d75')
 if i==0:
  text(990,886,'الأولى بقيمة الصادرات للعام الرابع؛',46)
  text(990,950,'١٫٩٤ مليار ريال صادراتنا في ٢٠٢٥.',46)
  label='حصة أبرز الدول من الإنتاج العالمي · ٢٠٢٤';y=1090
 else:
  text(990,890,'سوق صادرات التمور: ٢٫٦٣ مليار دولار',46)
  label='حصة أبرز الدول من قيمة الصادرات · ٢٠٢٤';y=1040
 text(990,y-68,label,36,True,green)
 for j,(country,pct,v) in enumerate(rows[i]):
  yy=y+j*78
  text(990,yy,country,49,j==0,green if j==0 else navy)
  d.rounded_rectangle((210,yy+14,700,yy+42),radius=8,fill='#dad6ce')
  w=round(490*v/20);d.rounded_rectangle((700-w,yy+14,700,yy+42),radius=8,fill=green if j==0 else '#93a8a0')
  text(190,yy,pct,46,True,green if j==0 else navy)
 if i==0:
  text(990,1530,'نصدّر ١٨٫٣٪ من إنتاجنا فقط.',52,True,red)
  text(990,1610,'نسبة كمية التصدير للإنتاج في ٢٠٢٤',31,c='#716e69')
 else:
  text(990,1470,'صادرات تونس قيمتها أكثر من',48,True,red)
  text(990,1535,'٣ أضعاف مصر، رغم أن مصر تنتج أكثر.',48,True,red)
  d.rounded_rectangle((82,1680,998,1790),radius=26,fill='#efdee0')
  text(868,1711,'شاركها مع صديقك اللي يحب التمر',36,True,red)
  d.line([(913,1755),(918,1730),(933,1717),(951,1715),(951,1700),(975,1723),(951,1747),(951,1732),(934,1735),(913,1755)],fill=red,width=5,joint='curve')
 badge(501,1810,78)
 im.save(P/f'card-{i:02}.jpg',quality=95,subsampling=0);im.resize((432,768)).save(P/f'preview-{i}.png')
 copy.append({'title':titles[i],'rows':rows[i]})
(P/'copy.json').write_text(json.dumps({'cards':copy,'approved_addition':'نصدّر ١٨٫٣٪ من إنتاجنا فقط (٢٠٢٤)','owner_removed':'المفاجأة'},ensure_ascii=False,indent=2))
