from PIL import Image, ImageDraw, ImageFont, ImageOps
from pathlib import Path
import json, base64
P=Path(__file__).parent
BG='#eeeae2'; NAVY='#15394e'; RED='#aa263a'; GREEN='#174b38'
im=Image.new('RGB',(1080,1920),BG);d=ImageDraw.Draw(im)
def font(n,b=False):return ImageFont.truetype('fonts/Almarai-'+('Bold' if b else 'Regular')+'.ttf',n)
def text(y,t,n=45,b=False,color=NAVY,x=990):
    assert d.textlength(t,font=font(n,b),direction='rtl')<=916,(t,n)
    d.text((x,y),t,font=font(n,b),fill=color,anchor='rt',direction='rtl',language='ar')
def badge(x,y,n):
    b=Image.open('images/brand/badge.png').convert('RGB').resize((n,n));m=Image.new('L',(n,n));ImageDraw.Draw(m).ellipse((0,0,n-1,n-1),fill=255);im.paste(b,(x,y),m)
badge(82,155,94);d.rectangle((876,169,990,179),fill=GREEN);text(200,'ملخص تنفيذي',30,True,GREEN)
title='إنستغرام يكمل ١٦ سنة… وبدأ بفكرة ثانية'
size=52
while d.textlength(title,font=font(size,True),direction='rtl')>916:size-=1
assert size>=43
text(306,title,size,True,RED)
# Existing archival images placed in the established template, no image generation.
panel=Image.new('RGB',(916,440),'white')
for name,x in [('feed',115),('logo',505)]:
    pic=ImageOps.contain(Image.open(P/(name+'.jpg')).convert('RGB'),(296,440))
    panel.paste(pic,(x,(440-pic.height)//2))
mask=Image.new('L',panel.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,439),28,fill=255);im.paste(panel,(82,390),mask)
text(850,'شعار إنستغرام وواجهة التطبيق في ٢٠١٠',25,color='#817d75')
bullets=[
'اليوم ٦ أكتوبر، ذكرى إطلاق إنستغرام عام ٢٠١٠.',
'بدايته كانت تطبيق «Burbn» لتسجيل الأماكن ومشاركة النشاطات والصور.',
'لاحظ المؤسسون إن الناس تستخدم بعض المزايا وتتجاهل الباقي؛ فاختصروا التطبيق وركزوا على مشاركة الصور.',
'وبعد نحو سنة ونص، أعلنت فيسبوك اتفاق شراء إنستغرام مقابل مليار دولار نقد وأسهم.'
]
y=921
for p in bullets:
    lines=[];line=''
    for w in p.split():
        trial=(line+' '+w).strip()
        if d.textlength(trial,font=font(45),direction='rtl')>855:lines.append(line);line=w
        else:line=trial
    if line:lines.append(line)
    d.ellipse((977,y+14,989,y+26),fill=GREEN)
    for line in lines:text(y,line,45,x=956);y+=60
    y+=22
assert y<1540,y
text(y+18,'أحيانًا تطوير الفكرة يبدأ بحذف الزايد.',42,True,RED)
cy=y+112
d.rounded_rectangle((82,cy,998,cy+88),radius=23,fill='#efdee0')
text(cy+24,'شاركها مع صديقك اللي تعجبه هذي المعلومة',32,True,RED,x=878)
d.line([(913,cy+64),(918,cy+39),(933,cy+26),(951,cy+24),(951,cy+13),(975,cy+35),(951,cy+58),(951,cy+43),(934,cy+46),(913,cy+64)],fill=RED,width=5,joint='curve')
badge(515,cy+118,50)
assert cy+168<1840
im.save(P/'card-00.jpg',quality=94,subsampling=0)
im.resize((540,960)).save(P/'preview.jpg',quality=92)
for name in ['card-00','feed','logo']:(P/(name+'.jpg.b64')).write_text(base64.b64encode((P/(name+'.jpg')).read_bytes()).decode())
(P/'copy.json').write_text(json.dumps({'title':title,'bullets':bullets,'closing':'أحيانًا تطوير الفكرة يبدأ بحذف الزايد.','cta':'شاركها مع صديقك اللي تعجبه هذي المعلومة','headline_font':size,'body_font':45,'layout_bottom':cy+168},ensure_ascii=False,indent=2))
print('headline_font',size,'body_font',45,'layout_bottom',cy+168)
