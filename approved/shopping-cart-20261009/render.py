from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
import json,hashlib,base64
P=Path(__file__).parent;R=P.parents[1]
BG='#eeeae2';NAVY='#15394e';RED='#aa263a';GREEN='#174b38'
im=Image.new('RGB',(1080,1920),BG);d=ImageDraw.Draw(im)
f=ImageFont.truetype(str(R/'fonts/Almarai-Bold.ttf'),40);bf=ImageFont.truetype(str(R/'fonts/Almarai-Bold.ttf'),30)
card={'bullets':[]}
def wrap(s,w):
 out=[];line=''
 for word in s.split():
  t=(line+' '+word).strip()
  if d.textlength(t,font=f,direction='rtl')>w:out.append(line);line=word
  else:line=t
 if line:out.append(line)
 return out
def text(s,y,key,col=NAVY,w=916,x=998):
 ls=wrap(s,w)
 assert len(ls)<=(1 if key in ('headline','cta') else 2),(key,ls)
 for n,line in enumerate(ls):d.text((x,y+62*n),line,font=f,fill=col,anchor='rt',direction='rtl',language='ar')
 block={'text':s,'size':40,'box':[x-w,y,x,y+len(ls)*62]}
 if key=='bullet':card['bullets'].append(block);d.ellipse((1008,y+16,1019,y+27),fill=col)
 else:card[key]=block
 return y+len(ls)*62
def badge(x,y,n):
 a=Image.open(R/'images/brand/badge.png').convert('RGB').resize((n,n));m=Image.new('L',(n,n));ImageDraw.Draw(m).ellipse((0,0,n-1,n-1),fill=255);im.paste(a,(x,y),m)
badge(82,100,92);d.rectangle((876,115,990,124),fill=GREEN);d.text((990,156),'ملخص تنفيذي',font=bf,fill=GREEN,anchor='rt',direction='rtl',language='ar')
y=text('عربة المقاضي… بدايتها زباين بالتمثيل!',264,'headline',RED)
py=y+36;src=Image.open(P/'photo.png').convert('RGB');photo=Image.new('RGB',(916,460),'#dedbd4');portrait=ImageOps.contain(src,(354,460));photo.paste(portrait,(0,0));detail=ImageOps.fit(src.crop((0,350,420,857)),(546,460));photo.paste(detail,(370,0));m=Image.new('L',photo.size);ImageDraw.Draw(m).rounded_rectangle((0,0,915,459),28,fill=255);im.paste(photo,(82,py),m)
cf=ImageFont.truetype(str(R/'fonts/Almarai-Bold.ttf'),26)
d.text((998,py+476),'سيلفان غولدمان مع عربات المقاضي — صورة أرشيفية',font=cf,fill='#88847d',anchor='rt',direction='rtl',language='ar')
y=text('في أمريكا عام ١٩٣٧م، صاحب متجر جرّب يخلي الزباين يدفعون مقاضيهم بدل ما يشيلونها.',py+534,'intro',GREEN)+22
for s in ['لاحظ إن الناس توقف تسوّق إذا ثقلت السلة، فوفّر لهم عربات بعجلات.','لكن كثير رفضوها! فدفع لرجال ونساء يمثلون دور زباين يتسوّقون بالعربات.','الناس شافوهم وبدؤوا يجربونها… وبعدها صارت متاجر ثانية تطلب العربات.']:
 y=text(s,y,'bullet')+24
y=text('حتى عربة المقاضي… احتاجت أحد يبدأ والباقين يلحقونه.',y+4,'closing',RED)+28
assert y+180<=1840,y
d.rounded_rectangle((82,y,998,y+102),24,fill='#efdee0')
text('شاركها مع صديقك اللي تعجبه المعلومة',y+24,'cta',RED,w=790,x=885)
pts=[(914,y+75)]
def curve(c1,c2,end):
 start=pts[-1]
 for k in range(1,21):
  t=k/20;u=1-t;pts.append(tuple(u*u*u*start[i]+3*u*u*t*c1[i]+3*u*t*t*c2[i]+t*t*t*end[i] for i in (0,1)))
curve((912,y+45),(927,y+31),(950,y+29));pts.extend([(950,y+16),(954,y+14),(981,y+39),(983,y+43),(981,y+47),(956,y+69),(950,y+67),(950,y+55)]);curve((936,y+55),(925,y+60),(917,y+76));d.polygon(pts,fill=RED);badge(512,y+125,56)
im.save(P/'card-00.jpg',quality=96,subsampling=0);im.resize((540,960)).save(P/'preview.jpg',quality=95)
card['sha256']=hashlib.sha256((P/'card-00.jpg').read_bytes()).hexdigest()
(P/'readability.json').write_text(json.dumps({'version':1,'typography_profile':'owner-bold40-20261008','visual_review':{'approved':False,'reference':'Pending mobile review'},'cards':[card]},ensure_ascii=False,indent=2))
print('CTA',y,'hash',card['sha256'])
