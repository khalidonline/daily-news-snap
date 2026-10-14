from pathlib import Path
import base64, json
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path.cwd(); OUT=ROOT/'approved/nvidia-sega-20261007'
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
    text(im,f'{num} من ٢',992,252,26,MUTED)
    text(im,title,992,320,53,RED,True)
    d.rounded_rectangle((82,430,998,940),30,fill='#e0e6e1')
    return im
def footer(im):
    d=ImageDraw.Draw(im);y=1640;d.rounded_rectangle((82,y,998,y+114),24,fill='#efdee0')
    text(im,'شاركها مع صديقك',865,y+14,38,RED,True)
    text(im,'اللي تعجبه هذي المعلومة',865,y+66,38,RED,True)
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


DATA=[{
 'title':'إنفيديا قربت ٦ تريليونات… وسيجا أنقذتها',
 'photo':'jensen-press.jpg','caption':'جنسن هوانغ، مؤسس إنفيديا — صورة رسمية',
 'bullets':['أمس سهمها سجّل قمة، وقيمتها قربت ٦ تريليونات دولار.',
 'بالتسعينات، اعترف مؤسسها لسيجا إن تقنية كرت الشاشة اللي اختاروها ما راح تنجح.',
 'طلعوا من المشروع، وسيجا دعمتهم بنحو ٥ ملايين دولار وقت كانوا مهددين بالانهيار.'],
 'closing':['دعم سيجا عطاهم فرصة… وباقي يطلعون','بمنتج الناس تشتريه.']},
 {'title':'من كروت الشاشة للذكاء الاصطناعي',
 'photo':'riva-original.jpg','caption':'كرت Diamond Viper V330 بتقنية RIVA 128',
 'bullets':['غيّروا خطتهم لكروت شاشة تسرّع ألعاب الكمبيوتر ثلاثية الأبعاد.',
 'في ١٩٩٧ أطلقوا RIVA 128؛ شحنوا أكثر من مليون وحدة خلال أول ٤ شهور.',
 'في ٢٠٠٦ فتحوا قوة كروتهم للأبحاث؛ ومنها وصلوا لتدريب الذكاء الاصطناعي.'],
 'closing':['اللي كان يرسم عالم اللعبة…','صار من أهم ركائز الذكاء الاصطناعي.']}]
records=[]
for i,c in enumerate(DATA):
 im=base(c['title'],('١','٢')[i]);d=ImageDraw.Draw(im)
 if i==0:
  photo=ImageOps.fit(Image.open(OUT/c['photo']).convert('RGB'),(916,510),method=Image.Resampling.LANCZOS,centering=(.5,0))
  mask=Image.new('L',photo.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,509),30,fill=255);im.paste(photo,(82,430),mask)
 else:
  # Complete photograph: proportional resize only, no crop/recolour/overlay.
  d.rectangle((82,430,998,940),fill=BG)
  photo=ImageOps.contain(Image.open(OUT/c['photo']).convert('RGB'),(916,510),Image.Resampling.LANCZOS)
  im.paste(photo,(82+(916-photo.width)//2,430))
 text(im,c['caption'],990,950,27,MUTED)
 b=[]
 for j,copy in enumerate(c['bullets']):
  # Keep quantities together rather than orphaning their units.
  copy=copy.replace('٦ تريليونات دولار','٦~تريليونات~دولار').replace('٥ ملايين دولار','٥~ملايين~دولار')
  lines=['']
  for w in copy.split():
   trial=(lines[-1]+' '+w).strip()
   if d.textlength(trial.replace('~',' '),font=font(48),direction='rtl')>880:lines.append(w)
   else:lines[-1]=trial
  lines=[line.replace('~',' ') for line in lines]
  assert len(lines)<=2,(copy,lines)
  y=1010+j*166
  d.ellipse((983,y+17,996,y+30),fill=GREEN)
  for k,line in enumerate(lines):text(im,line,965,y+k*64,48)
  b.append({'text':'\n'.join(lines),'size':48,'box':[82,y,965,y+130]})
 for j,line in enumerate(c['closing']):text(im,line,992,1505+j*59,46,RED,True)
 footer(im)
 if i==0:badge(im,512,1790,56)
 else:
  from publishing_v2.autopilot.credits import public_attribution_layout
  rows=['Mathías Tabó · Photo: CC BY-SA 4.0','commons.wikimedia.org/?curid=38130580','creativecommons.org/licenses/by-sa/4.0/','Resized only · Photo remains CC BY-SA 4.0']
  for j,row in enumerate(rows):d.text((540,1770+j*28),row,font=font(24),fill=MUTED,anchor='mt')
 save(im,i)
 records.append({'headline':{'text':c['title'],'size':53,'box':[82,320,998,396]},'bullets':b,'cta':{'text':'شاركها مع صديقك اللي تعجبه هذي المعلومة','size':38,'box':[82,1654,865,1760]}})
(OUT/'copy.json').write_text(json.dumps(DATA,ensure_ascii=False,indent=2))
(OUT/'layout.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
