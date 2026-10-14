from PIL import Image,ImageDraw,ImageFont,ImageOps
from pathlib import Path
import json
P=Path(__file__).parent
font=lambda n,b=False:ImageFont.truetype('fonts/Almarai-'+('Bold' if b else 'Regular')+'.ttf',n)
navy='#15394e';green='#174b38';red='#aa263a';bg='#eeeae2'
cards=[{'title':['المراعي أعلنت اليوم','مبيعات فوق ٦ مليارات…','كيف كبرت؟'],'bullets':['البداية: عام ١٩٧٧ بدأت بإنتاج الحليب الطازج من ٣٠٠ بقرة.','المنتجات: من الحليب والألبان للعصائر والمخبوزات والدواجن؛ وصلت إلى ٦٧٠ منتج تحت ٢٠ علامة تجارية.','الانتشار: بدأت للسوق السعودي، ثم توسعت للخليج ومصر والأردن.']},{'title':['أول مليار أخذ ٢٠ سنة…','واليوم فوق ٦ مليارات','في ٣ أشهر'],'bullets':['احتاجت نحو ٢٠ سنة حتى وصلت مبيعاتها السنوية إلى مليار ريال.','وسّعت نشاطها بشراء «المخابز الغربية» وراء لوزين، ثم «هادكو» للدواجن.','واليوم ٤ أكتوبر أعلنت مبيعات ٦٫١٩ مليار ريال في الربع الثالث وحده.']}]
for i,card in enumerate(cards):
 im=Image.new('RGB',(1080,1920),bg);d=ImageDraw.Draw(im)
 def text(x,y,s,size=50,b=False,c=navy):
  assert d.textlength(s,font=font(size,b),direction='rtl')<=920,(s,size)
  d.text((x,y),s,font=font(size,b),fill=c,anchor='rt',direction='rtl',language='ar')
 def badge(x,y,n):
  b=Image.open('images/brand/badge.png').convert('RGB').resize((n,n));m=Image.new('L',(n,n));ImageDraw.Draw(m).ellipse((0,0,n-1,n-1),fill=255);im.paste(b,(x,y),m)
 badge(82,126,128);d.rectangle((858,156,990,166),fill=green)
 text(990,196,'ملخص تنفيذي · '+('معلومة' if i==0 else 'قصة'),30,True,green);text(990,261,['١ من ٢','٢ من ٢'][i],28,c='#827e77')
 for j,t in enumerate(card['title']):text(990,325+j*79,t,59,True,red)
 ph=ImageOps.fit(Image.open(P/f'photo-{i}.webp').convert('RGB'),(916,350),centering=(.5,.08 if i==0 else .22));mask=Image.new('L',ph.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,349),radius=28,fill=255);im.paste(ph,(82,585),mask)
 text(990,953,['إحدى مزارع المراعي — صورة أرشيفية','جناح المراعي في معرض — صورة أرشيفية'][i],25,c='#817d75')
 y=1015
 for k,s in enumerate(card['bullets']):
  lines=[];line=''
  for w in s.split():
   trial=(line+' '+w).strip()
   if d.textlength(trial,font=font(50),direction='rtl')>840:lines.append(line);line=w
   else:line=trial
  lines.append(line)
  d.ellipse((974,y+20,988,y+34),fill=green)
  for ln in lines:text(950,y,ln,50);y+=66
  y+=27
 assert y<1680,y
 if i==1:
  d.rounded_rectangle((82,1680,998,1790),radius=26,fill='#efdee0')
  text(868,1715,'شاركها مع صديقك اللي يحب قصص الشركات',32,True,red)
  d.line([(913,1755),(918,1730),(933,1717),(951,1715),(951,1700),(975,1723),(951,1747),(951,1732),(934,1735),(913,1755)],fill=red,width=5,joint='curve')
 badge(501,1810,78)
 im.save(P/f'card-{i:02}.jpg',quality=95,subsampling=0);im.resize((432,768)).save(P/f'preview-{i}.png')
(P/'copy.json').write_text(json.dumps({'cards':cards,'cta':'شاركها مع صديقك اللي يحب قصص الشركات'},ensure_ascii=False,indent=2))
