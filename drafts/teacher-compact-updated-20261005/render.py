from PIL import Image,ImageDraw,ImageFont,ImageOps
from pathlib import Path
import json
P=Path(__file__).parent
BG='#eeeae2'; NAVY='#15394e'; RED='#aa263a'; GREEN='#174b38'
font=lambda n,b=False:ImageFont.truetype('fonts/Almarai-'+('Bold' if b else 'Regular')+'.ttf',n)
cards=[dict(slug='neom',title='خبر ملعب نيوم… وطوكيو غيّرت خطتها',caption='ملعب طوكيو بعد اكتماله — صورة أرشيفية',bullets=['أمس، نشرت رويترز عن مصادر خبر تعليق مشروع ملعب نيوم لكأس العالم ٢٠٣٤؛ ما صدر تأكيد رسمي للتعليق.','اليابان سبق غيّرت خطتها: ألغت تصميم زها حديد لملعب طوكيو الأولمبي بعد ارتفاع تكلفته.','اختارت تصميم جديد في ٢٠١٥، واكتمل الملعب في ٢٠١٩ ضمن ميزانية البناء المحددة.'],end='تغيير الخطة أحيانًا أفضل للمشروع من الاستمرار فيها',cta='شاركها مع صديقك اللي تعجبه هذي المعلومة'),dict(slug='teacher',title='يوم المعلّم… ومشروع الـ٥٠٠ ريال',caption='منصور المنصور في تكريم جائزة المعلّم العالمية ٢٠٢٥',bullets=['اليوم ٥ أكتوبر، يوم المعلّم؛ ومنصور المنصور معلّم من الأحساء.','تعاون مع جمعيات لتوفير ٥٠٠ ريال قرض بدون فوائد للطالب، يبدأ فيها كشك أو مشروع صغير.','خلال شهرين، حقق الطلاب المشاركون دخل بين ١٣٠٠ و١٥٠٠ ريال من مشاريعهم.','وفي ٢٠٢٥، فاز منصور بجائزة المعلّم العالمية، وقيمتها مليون دولار.'],end='أثر المعلّم يكبر يوم يوصل لحياة طلابه.',cta='شاركها مع صديقك اللي تعجبه هذي المعلومة')]
cards=cards[1:]
for c in cards:
 im=Image.new('RGB',(1080,1920),BG);d=ImageDraw.Draw(im)
 def text(y,t,n=46,b=False,color=NAVY,x=990):
  assert d.textlength(t,font=font(n,b),direction='rtl')<=916,(t,n)
  d.text((x,y),t,font=font(n,b),fill=color,anchor='rt',direction='rtl',language='ar')
 def badge(x,y,n):
  b=Image.open('images/brand/badge.png').convert('RGB').resize((n,n));m=Image.new('L',(n,n));ImageDraw.Draw(m).ellipse((0,0,n-1,n-1),fill=255);im.paste(b,(x,y),m)
 badge(82,155,94);d.rectangle((876,169,990,179),fill=GREEN);text(200,'ملخص تنفيذي',30,True,GREEN)
 text(314,c['title'],55,True,RED)
 photo=ImageOps.fit(Image.open(P/(c['slug']+'-photo.jpg')).convert('RGB'),(916,370),centering=(0.5,0.22) if c['slug']=='teacher' else (0.5,0.5));mask=Image.new('L',photo.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,369),28,fill=255);im.paste(photo,(82,408),mask);text(798,c['caption'],25,color='#817d75')
 y=867
 for p in c['bullets']:
  lines=[];line=''
  for w in p.split():
   trial=(line+' '+w).strip()
   if d.textlength(trial,font=font(45),direction='rtl')>855:lines.append(line);line=w
   else:line=trial
  if line:lines.append(line)
  d.ellipse((977,y+14,989,y+26),fill=GREEN)
  for line in lines:text(y,line,45,x=956);y+=61
  y+=25
 assert y<1550,(c['slug'],y)
 for j,line in enumerate(c['end'].splitlines()):text(y+35+j*60,line,38,True,RED)
 d.rounded_rectangle((82,y+140,998,y+228),radius=23,fill='#efdee0');text(y+164,c['cta'],32,True,RED,x=878)
 d.line([(x,yy+y-1610) for x,yy in [(913,1810),(918,1785),(933,1772),(951,1770),(951,1759),(975,1781),(951,1804),(951,1789),(934,1792),(913,1810)]],fill=RED,width=5,joint='curve')
 badge(510,y+290,50);im.save(P/(c['slug']+'.jpg'),quality=95,subsampling=0);im.resize((540,960)).save(P/(c['slug']+'-preview.jpg'),quality=92)
(P/'copy.json').write_text(json.dumps({'status':'DESIGN_REVIEW_ONLY','publish_approved':False,'cards':cards},ensure_ascii=False,indent=2))