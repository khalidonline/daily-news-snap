import os,sys,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
os.environ.update(THEME='light',FONT_FAMILY='Almarai');sys.path.insert(0,str(Path.cwd()))
import news_bot
P=Path('drafts/disney-short-v2-20261002');F=Path('fonts')
font=lambda n,b=False:ImageFont.truetype(str(F/('Almarai-Bold.ttf' if b else 'Almarai-Regular.ttf')),n)
navy='#15394e';green='#174b38';red='#aa263a';ink='#263e4b';bg='#eeeae2'
cards=[{
 'title':['قبل ميكي…','ديزني خسر أرنب ناجح'],
 'points':['أوزوالد كان نجم ديزني، لكن حقوقه كانت عند يونيفرسال.','تعثّر تجديد العقد عام ١٩٢٨، فاحتاج ديزني شخصية يملكها.','ابتكر ديزني وفريقه ميكي ماوس… لكن أول فيلمين ما لقوا موزّع.'],
 'caption':'ميكي ماوس في «ستيمبوت ويلي» — ١٩٢٨'},
 {'title':['ميكي نجح… والأرنب رجع','بعد ٧٨ سنة'],
 'points':['في «ستيمبوت ويلي»، ربطوا الحركة بالموسيقى والمؤثرات الصوتية.','نجح الفيلم، وبدأ ميكي يصير نجم.','عام ٢٠٠٦، رجعت حقوق أوزوالد لديزني… واجتمع الأرنب وميكي تحت شركة وحدة.'],
 'caption':'أوزوالد في فيلم ديزني القصير — ٢٠٢٢',
 'share':'شاركها مع صديقك اللي يحب ديزني'}]
for i,c in enumerate(cards,1):
 im=Image.new('RGB',(1080,1920),bg);d=ImageDraw.Draw(im)
 news_bot.draw_brand_badge(im,xy=(82,126),size=128)
 d.rounded_rectangle((858,156,990,166),radius=4,fill=green)
 def text(x,y,s,f,color=ink,anchor='ra'):
  d.text((x,y),s,font=f,fill=color,anchor=anchor,direction='rtl',language='ar')
 text(988,195,'ملخص تنفيذي · قصة',font(30,True),green)
 text(988,260,'١ من ٢' if i==1 else '٢ من ٢',font(28), '#827e77')
 for j,line in enumerate(c['title']):text(990,330+j*88,line,font(68,True),navy)
 ph=ImageOps.fit(Image.open(P/f'photo-{i}.jpg').convert('RGB'),(916,420),centering=(.5,.5))
 mask=Image.new('L',ph.size,0);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,419),radius=30,fill=255);im.paste(ph,(82,540),mask)
 text(998,980,c['caption'],font(25),'#817d75')
 f=font(52); y=1060
 for n,point in enumerate(c['points']):
  words=point.split();lines=[];line=''
  for w in words:
   t=(line+' '+w).strip()
   if d.textlength(t,font=f,direction='rtl')>850:lines.append(line);line=w
   else:line=t
  if line:lines.append(line)
  assert len(lines)<=2,(i,n,lines)
  d.ellipse((972,y+20,990,y+38),fill=green)
  for j,l in enumerate(lines):text(944,y+j*72,l,f,ink)
  y+=len(lines)*72+38
 assert y<1650,y
 if c.get('share'):
  text(990,1700,c['share'],font(40,True),green)
 news_bot.closing_seal(im,1820,size=100)
 im.save(P/f'card-{i:02}.jpg',quality=96,subsampling=0)
 print(i,'text_bottom',y)
(P/'copy.json').write_text(json.dumps({'status':'DRAFT_REVIEW_ONLY_NOT_APPROVED_FOR_PUBLICATION','design':'two cards; three short bullets; 52px fixed body; established brand','cards':cards,'sources':['https://thewaltdisneycompany.com/news/oswald-the-lucky-rabbit-anniversary-disney/','https://thewaltdisneycompany.com/news/happy-85th-anniversary-oswald-the-lucky-rabbit/'],'replaces_nothing':True},ensure_ascii=False,indent=2))
