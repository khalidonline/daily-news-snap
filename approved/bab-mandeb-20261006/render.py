from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import json, base64, hashlib
P=Path(__file__).parent
BG='#eeeae2'; NAVY='#15394e'; RED='#aa263a'; GREEN='#174b38'
im=Image.new('RGB',(1080,1920),BG); d=ImageDraw.Draw(im)
def font(n,b=False):return ImageFont.truetype('fonts/Almarai-'+('Bold' if b else 'Regular')+'.ttf',n)
def text(y,t,n=43,b=False,color=NAVY,x=990):
    assert d.textlength(t,font=font(n,b),direction='rtl')<=916,(t,n)
    d.text((x,y),t,font=font(n,b),fill=color,anchor='rt',direction='rtl',language='ar')
def badge(x,y,n):
    b=Image.open('images/brand/badge.png').convert('RGB').resize((n,n));m=Image.new('L',(n,n));ImageDraw.Draw(m).ellipse((0,0,n-1,n-1),fill=255);im.paste(b,(x,y),m)
badge(82,155,94);d.rectangle((876,169,990,179),fill=GREEN);text(200,'ملخص تنفيذي',30,True,GREEN)
title='أخبار اليمن… ليه باب المندب مهم؟'
text(296,title,51,True,RED)
# Geographically grounded schematic using public-domain Natural Earth land.
mp=Image.new('RGB',(916,450),'#dce7e8');md=ImageDraw.Draw(mp)
def xy(lon,lat): return (220+(lon+22)*5.48,(43-lat)*5.48)
land=json.loads(Path('/tmp/bab-land.geojson').read_text())
for feat in land['features']:
    g=feat['geometry'];polys=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
    for poly in polys:md.polygon([xy(*pt) for pt in poly[0]],fill='#c9c5b8')
direct=[(61,8),(52,11),(45,12),(43.3,12.6),(40,18),(36,25),(32.55,29.9),(32.3,31.3),(24,34),(10,37),(-6,36)]
cape=[(61,8),(54,-8),(46,-24),(30,-36),(17,-36),(8,-28),(-3,-5),(-20,16),(-12,32),(-6,36)]
md.line([xy(*pt) for pt in cape],fill=RED,width=5,joint='curve')
md.line([xy(*pt) for pt in direct],fill=GREEN,width=6,joint='curve')
def ml(t,lon,lat,n=25,c=NAVY):md.text(xy(lon,lat),t,font=font(n,True),fill=c,anchor='mm',direction='rtl')
ml('أفريقيا',15,7,34);ml('آسيا',51,32,31);ml('أوروبا',8,40,25)
bx,by=xy(43.3,12.6);md.ellipse((bx-7,by-7,bx+7,by+7),fill=RED)
md.line([(bx,by),(bx+40,by+28)],fill=NAVY,width=2);ml('باب المندب',51,4,25)
sx,sy=xy(32.55,29.9);md.ellipse((sx-5,sy-5,sx+5,sy+5),fill=GREEN);ml('السويس',40,38,23)
mask=Image.new('L',mp.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,449),26,fill=255);im.paste(mp,(82,392),mask)
text(859,'عبر البحر الأحمر',27,True,GREEN,x=990)
text(859,'حول أفريقيا',27,True,RED,x=550)
text(901,'رسم مبسط للمسارين — مو تتبع حي للسفن',23,color='#817d75')
bullets=[
'أمس ٥ أكتوبر، نقلت رويترز عن مصادر تقدم قوات الحكومة اليمنية قرب باب المندب.',
'عرضه بأضيق نقطة نحو ٢٩ كم؛ ويربط البحر الأحمر بخليج عدن والطريق إلى قناة السويس.',
'قبل اضطرابات أواخر ٢٠٢٣، مر بمسار البحر الأحمر نحو ٣٠٪ من حركة الحاويات العالمية.',
'إذا تعطّل المرور، تضطر سفن تلف حول أفريقيا؛ فتطول الرحلة وتزيد تكلفة الشحن.'
]
y=966
for p in bullets:
    lines=[];line=''
    for w in p.split():
        trial=(line+' '+w).strip()
        if d.textlength(trial,font=font(43),direction='rtl')>855:lines.append(line);line=w
        else:line=trial
    if line:lines.append(line)
    d.ellipse((977,y+13,989,y+25),fill=GREEN)
    for line in lines:text(y,line,43,x=956);y+=57
    y+=22
assert y<=1530,y
text(y+14,'حتى لو السويس مفتوحة… الوصول لها ممكن يتعطّل.',35,True,RED)
cy=y+105
d.rounded_rectangle((82,cy,998,cy+88),radius=23,fill='#efdee0')
text(cy+24,'شاركها مع صديقك اللي تعجبه هذي المعلومة',32,True,RED,x=878)
d.line([(913,cy+64),(918,cy+39),(933,cy+26),(951,cy+24),(951,cy+13),(975,cy+35),(951,cy+58),(951,cy+43),(934,cy+46),(913,cy+64)],fill=RED,width=5,joint='curve')
badge(515,cy+116,50)
assert cy+166<1840
im.save(P/'card-00.jpg',quality=94,subsampling=0)
im.resize((540,960)).save(P/'preview.jpg',quality=92)
(P/'card-00.jpg.b64').write_text(base64.b64encode((P/'card-00.jpg').read_bytes()).decode())
(P/'copy.json').write_text(json.dumps({'title':title,'bullets':bullets,'approved_by':'Khalid: انشر, 2026-10-06; text/layout based on approved one-card draft','visual':'Natural Earth public-domain geographic schematic; approximate routes, not live tracking','sources':['https://www.reuters.com/world/yemeni-government-forces-seize-district-by-bab-el-mandeb-military-sources-say-2026-10-05/','https://blogs.worldbank.org/en/developmenttalk/navigating-troubled-waters--the-red-sea-shipping-crisis-and-its-','https://www.eia.gov/todayinEnergy/detail.php?id=41073','https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson']},ensure_ascii=False,indent=2))
print('layout_end',cy+166,'sha256',hashlib.sha256((P/'card-00.jpg').read_bytes()).hexdigest())
