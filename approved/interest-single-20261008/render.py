from pathlib import Path
import base64, json
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path.cwd(); OUT=ROOT/'approved/interest-single-20261008'
BG='#eeeae2'; NAVY='#15394e'; RED='#aa263a'; GREEN='#174b38'; MUTED='#827f77'
def font(size,bold=False):
    return ImageFont.truetype(str(ROOT/'fonts'/('Almarai-Bold.ttf' if bold else 'Almarai-Regular.ttf')),size)
def text(im,s,x,y,size=48,color=NAVY,bold=False,anchor='rt'):
    d=ImageDraw.Draw(im)
    assert d.textlength(s,font=font(size,bold),direction='rtl')<=916,s
    d.text((x,y),s,font=font(size,bold),fill=color,anchor=anchor,direction='rtl',language='ar')
def badge(im,x,y,n):
    b=Image.open(ROOT/'images/brand/badge.png').convert('RGB').resize((n,n))
    m=Image.new('L',(n,n));ImageDraw.Draw(m).ellipse((0,0,n-1,n-1),fill=255);im.paste(b,(x,y),m)
def arrow(d,points,color,width=7):
    import math
    d.line(points,fill=color,width=width,joint='curve');x,y=points[-1];px,py=points[-2];a=math.atan2(y-py,x-px)
    d.polygon([(x,y),(x-22*math.cos(a-.5),y-22*math.sin(a-.5)),(x-22*math.cos(a+.5),y-22*math.sin(a+.5))],fill=color)
def base(title,num):
    im=Image.new('RGB',(1080,1920),BG);d=ImageDraw.Draw(im)
    badge(im,82,148,94);d.rectangle((876,169,990,179),fill=GREEN)
    text(im,'ملخص تنفيذي',992,200,30,GREEN,True)
    text(im,'١ من ١',992,252,26,MUTED)
    text(im,title,992,320,53,RED,True)
    d.rounded_rectangle((82,430,998,940),30,fill='#e0e6e1')
    return im
def footer(im):
    d=ImageDraw.Draw(im);y=1700;d.rounded_rectangle((82,y,998,y+114),24,fill='#efdee0')
    text(im,'شاركها مع صديقك اللي تعجبه المعلومة',887,y+36,38,RED,True)
    # Solid, curved sharing arrow matching the approved visual style.
    points=[(914,y+78)]
    def curve(c1,c2,end):
        start=points[-1]
        for k in range(1,21):
            t=k/20;u=1-t
            points.append(tuple(u*u*u*start[i]+3*u*u*t*c1[i]+3*u*t*t*c2[i]+t*t*t*end[i] for i in (0,1)))
    curve((912,y+48),(927,y+34),(950,y+32))
    points.extend([(950,y+19),(954,y+17),(981,y+42),(983,y+46),(981,y+50),(956,y+72),(950,y+70),(950,y+58)])
    curve((936,y+58),(925,y+63),(917,y+79))
    d.polygon(points,fill=RED)
    # Bottom is reserved for the photo rights notice on card 2.
def block(im,y,head,lines):
    text(im,head,990,y,46,GREEN,True)
    for i,s in enumerate(lines):text(im,s,990,y+68+i*65,48)
def save(im,n):
    im.save(OUT/f'card-{n:02}.jpg',quality=96,subsampling=0)
    im.resize((540,960)).save(OUT/f'preview-{n:02}.jpg',quality=94)
    (OUT/f'card-{n:02}.jpg.b64').write_text(base64.b64encode((OUT/f'card-{n:02}.jpg').read_bytes()).decode())



import hashlib
im=base('ليش يرفعون الفائدة إذا غلت الأسعار؟','١');d=ImageDraw.Draw(im)
photo=ImageOps.fit(Image.open(OUT/'eccles.jpg').convert('RGB'),(916,350),method=Image.Resampling.LANCZOS)
d.rectangle((82,430,998,940),fill=BG)
mask=Image.new('L',photo.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,349),30,fill=255);im.paste(photo,(82,430),mask)
text(im,'مبنى الفيدرالي الأمريكي — صورة أرشيفية',992,795,27,MUTED)
lines=[('أمس نُشر محضر الفيدرالي، والفائدة الأمريكية',870),('اليوم بين ٣٫٧٥٪ و٤٪. وش علاقتها بالغلا؟',932)]
for line,y in lines:text(im,line,992,y,48)
blocks=[('الفائدة الأعلى ترفع تكلفة القروض:',1035,['لو ناوي تشتري سيارة بالتقسيط، التمويل','الأغلى قد يخليك تأجل الشراء.']),('تأجيل الشراء يخفف الطلب:',1280,['وإذا أجّل ناس وشركات كثيرة مشترياتهم،','يخف الطلب ويصير رفع الأسعار أصعب.'])]
records=[]
for head,y,rows in blocks:
 text(im,head,992,y,48,GREEN,True)
 for k,line in enumerate(rows):text(im,line,992,y+65+k*62,48)
 records.append({'text':'\n'.join(rows),'size':48,'box':[82,y+65,998,y+255]})
text(im,'الهدف إن الأسعار ترتفع بشكل أبطأ…',992,1555,46,RED,True)
text(im,'مو شرط تنزل.',992,1610,46,RED,True)
footer(im);badge(im,512,1840,56);save(im,0)
(OUT/'copy.json').write_text(json.dumps({'headline':'ليش يرفعون الفائدة إذا غلت الأسعار؟','intro':[x[0] for x in lines],'blocks':blocks,'closing':'الهدف إن الأسعار ترتفع بشكل أبطأ… مو شرط تنزل.','cta':'شاركها مع صديقك اللي تعجبه المعلومة'},ensure_ascii=False,indent=2))
(OUT/'readability.json').write_text(json.dumps({'version':1,'visual_review':{'approved':False,'reference':'pending'},'cards':[{'sha256':hashlib.sha256((OUT/'card-00.jpg').read_bytes()).hexdigest(),'headline':{'text':'ليش يرفعون الفائدة إذا غلت الأسعار؟','size':53,'box':[82,320,998,396]},'bullets':records,'cta':{'text':'شاركها مع صديقك اللي تعجبه المعلومة','size':38,'box':[82,1736,887,1810]}}]},ensure_ascii=False,indent=2))
