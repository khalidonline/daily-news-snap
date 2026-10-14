from pathlib import Path
import base64, json
from PIL import Image, ImageDraw, ImageFont

ROOT=Path.cwd(); OUT=Path(__file__).parent
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
    text(im,title,992,320,54,RED,True)
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
    badge(im,512,1790,56)
def block(im,y,head,lines):
    text(im,head,990,y,46,GREEN,True)
    for i,s in enumerate(lines):text(im,s,990,y+68+i*65,48)
def save(im,n):
    im.save(OUT/f'card-{n:02}.jpg',quality=96,subsampling=0)
    im.resize((540,960)).save(OUT/f'preview-{n:02}.jpg',quality=94)
    (OUT/f'card-{n:02}.jpg.b64').write_text(base64.b64encode((OUT/f'card-{n:02}.jpg').read_bytes()).decode())

im=base('كيف يشوف الرادار الصاروخ؟','١');d=ImageDraw.Draw(im)
# Abstract labelled schematic: outbound radio pulse, reflected return, target.
d.line((180,846,370,846),fill=NAVY,width=8);d.line((275,840,275,745),fill=NAVY,width=12)
d.arc((190,626,344,780),20,165,fill=NAVY,width=12);d.line((265,737,313,665),fill=NAVY,width=8)
arrow(d,[(320,660),(475,568),(715,568)],GREEN)
arrow(d,[(719,630),(495,700),(350,756)],RED)
d.rounded_rectangle((725,555,875,610),20,fill=NAVY);d.polygon([(875,555),(922,582),(875,610)],fill=NAVY)
text(im,'الهدف',895,480,38,NAVY,True)
text(im,'موجات مرسلة',641,485,35,GREEN,True)
text(im,'إشارة راجعة',744,710,35,RED,True)
text(im,'الرادار',340,862,36,NAVY,True)
block(im,1000,'يرسل موجات… ويقيس رجعتها',[
    'الموجات ترتد من الهدف؛ وقت رجوعها',
    'يحدد بُعده، وتتابعها يكشف حركته.'])
block(im,1240,'متى يلتقطه؟ ما فيه مسافة ثابتة',[
    'إذا دخل تغطيته ورجعت إشارة كافية؛',
    'ارتفاعه وانحناء الأرض يأثران على الرصد.'])
text(im,'يعرف مكانه من الإشارة… مو من صورة.',992,1510,46,RED,True)
footer(im);save(im,0)

im=base('ممكن ينكشف من لحظة الإطلاق؟','٢');d=ImageDraw.Draw(im)
# A process schematic, not a deployment or interception-geometry claim.
for x in (185,455,725):d.rounded_rectangle((x,560,x+165,725),24,fill=BG)
# Satellite symbol.
d.rectangle((215,610,245,674),fill=GREEN);d.rectangle((290,610,320,674),fill=GREEN);d.rounded_rectangle((250,620,285,665),6,fill=NAVY)
# Radar symbol.
d.line((540,675,540,640),fill=NAVY,width=8);d.arc((495,590,580,669),15,165,fill=NAVY,width=8);d.line((505,682,575,682),fill=NAVY,width=6)
# Abstract meeting paths.
arrow(d,[(750,600),(802,650)],RED,6);arrow(d,[(755,688),(802,650)],GREEN,6);d.ellipse((792,640,812,660),fill=RED)
arrow(d,[(354,641),(443,641)],NAVY);arrow(d,[(624,641),(713,641)],NAVY)
text(im,'قمر صناعي',345,755,34,GREEN,True)
text(im,'متابعة رادارية',625,755,34,GREEN,True)
text(im,'اعتراض',865,755,34,GREEN,True)
text(im,'رسم مبسّط لشبكة إنذار واعتراض',930,858,31,MUTED)
block(im,980,'البداية ممكن تكون من الفضاء',[
    'أقمار الإنذار تلتقط حرارة عادم الصاروخ',
    'وقت الإطلاق، وترسل تنبيه مبكر.'])
block(im,1215,'بعدها الرصد يتحوّل لاعتراض',[
    'الرادارات تتابع مساره؛ والصاروخ الدفاعي',
    'يتوجّه لنقطة الالتقاء مع تحديثات مستمرة.'])
text(im,'الاعتراض شغل شبكة… مو رادار بس.',992,1495,46,RED,True)
text(im,'شرح عام؛ القدرات تختلف حسب المنظومة',992,1570,29,MUTED)
footer(im);save(im,1)
(OUT/'review.json').write_text(json.dumps({'status':'DRAFT_NOT_PUBLISHED','style':'Precise schematic diagrams, not real-event photographs or operational schematics','scope':'General radar and missile-warning principles; no Riyadh event reference','sources':['https://www.weather.gov/bmx/radar_aboutnwsradar_howdoesitwork','https://www.weather.gov/media/epz/mesonet/CWOP-WMO8.pdf','https://www.spaceforce.mil/about-us/fact-sheets/article/2197746/space-based-infrared-system/','https://www.mda.mil/system/thaad.html'],'paid_model_requests':0},indent=2))
