from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
P=Path(__file__).parent
BG='#eeeae2';NAVY='#15394e';RED='#aa263a';GREEN='#174b38'
im=Image.new('RGB',(1080,1920),BG);d=ImageDraw.Draw(im)
font=ImageFont.truetype(str(P/'fonts/Almarai-Bold.ttf'),40)
brandfont=ImageFont.truetype(str(P/'fonts/Almarai-Bold.ttf'),30)
def wrap(s,width=916):
 lines=[];line=''
 for w in s.split():
  trial=(line+' '+w).strip()
  if d.textlength(trial,font=font,direction='rtl')>width:
   lines.append(line);line=w
  else:line=trial
 if line:lines.append(line)
 return lines
def paragraph(s,y,color=NAVY,width=916,x=998):
 lines=wrap(s,width)
 for line in lines:
  d.text((x,y),line,font=font,fill=color,anchor='rt',direction='rtl',language='ar');y+=62
 return y
def badge(x,y,n):
 a=Image.open(P/'images/brand/badge.png').convert('RGB').resize((n,n));m=Image.new('L',(n,n));ImageDraw.Draw(m).ellipse((0,0,n-1,n-1),fill=255);im.paste(a,(x,y),m)
badge(82,100,92);d.rectangle((876,115,990,124),fill=GREEN)
d.text((990,156),'ملخص تنفيذي',font=brandfont,fill=GREEN,anchor='rt',direction='rtl',language='ar')
y=paragraph('خويّك اللي ينام بأي مكان… فاتته البطولة!',264,RED)
photo_y=y+36
photo=ImageOps.fit(Image.open(P/'sleep-event.jpg').convert('RGB'),(916,380),method=Image.Resampling.LANCZOS)
m=Image.new('L',photo.size);ImageDraw.Draw(m).rounded_rectangle((0,0,915,379),28,fill=255);im.paste(photo,(82,photo_y),m)
y=photo_y+410
y=paragraph('في طوكيو سوّوا مسابقة يوم ٥ أكتوبر: مين ينام أسرع ويغطّ بنوم أعمق؟',y,GREEN)
d.ellipse((1008,y+16,1019,y+27),fill=NAVY)
y=paragraph('الجائزة أكثر من مليونين ين — حوالي ٥٢ ألف ريال!',y)
y+=30
for s in ['عطوهم ٩٠ دقيقة، والأجهزة تقيس نومهم… يعني تسوي نفسك نايم ما تمشي!','وبعضهم جاب دميته معه؛ داخل البطولة بكامل التجهيزات!','الهدف يلفتون الانتباه لقلة النوم في اليابان.']:
 d.ellipse((1008,y+16,1019,y+27),fill=NAVY)
 y=paragraph(s,y);y+=28
y+=10
y=paragraph('اللي كل ما دقيت عليه قال «كنت نايم»… يمكن طلع موهوب وحنا نظلمه.',y,RED)
y+=36
cta='شاركها مع صديقك اللي تعجبه المعلومة'
assert len(wrap(cta,790))==1
assert y+155<1880,y
d.rounded_rectangle((82,y,998,y+102),24,fill='#efdee0')
paragraph(cta,y+29,RED,width=790,x=885)
points=[(914,y+75)]
def curve(c1,c2,end):
 start=points[-1]
 for k in range(1,21):
  t=k/20;u=1-t;points.append(tuple(u*u*u*start[i]+3*u*u*t*c1[i]+3*u*t*t*c2[i]+t*t*t*end[i] for i in (0,1)))
curve((912,y+45),(927,y+31),(950,y+29));points.extend([(950,y+16),(954,y+14),(981,y+39),(983,y+43),(981,y+47),(956,y+69),(950,y+67),(950,y+55)]);curve((936,y+55),(925,y+60),(917,y+76));d.polygon(points,fill=RED)
badge(512,y+125,56)
im.save(P/'Sleep-Competition-v4.jpg',quality=96,subsampling=0)
im.resize((540,960)).save(P/'preview-v4.jpg',quality=95)
print('CTA y',y,'font Almarai Bold 40; body and caption all navy; semantic blocks auto wrapped')
