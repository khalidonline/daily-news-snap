from PIL import Image,ImageDraw,ImageFont,ImageOps
from pathlib import Path
import json
P=Path(__file__).parent;B=P.parent/'berlin-design'
font=lambda n,b=False:ImageFont.truetype(str(B/('Almarai-Bold.ttf' if b else 'Almarai-Regular.ttf')),n)
navy='#143B56';red='#AB263A';green='#245741';bg='#EEEAE2'
cards=[{'title':['أمس تراجع سهم نايكي…','هل كثّرت من أحذيتها المشهورة؟'],'photo':'jordan.jpg','caption':'جوردن ١ «شيكاغو» — إعادة إصدار لموديل كلاسيكي','points':['مبيعاتها نزلت ٤٪ عن نفس الفترة السنة الماضية.','رئيس الشركة وصف موديلات اللبس اليومي بأنها صارت متشابهة بشكل كبير.','نايكي أعلنت إنها بتقلّل إصدارات جوردن القديمة المعاد طرحها؛ كثرة الإصدارات ما ضمنت استمرار الطلب.']},{'title':['الحذاء نجح…','بس تكراره ما يكفي'],'photo':'running.jpg','caption':'بيغاسوس بلس ٢ — من أحذية الجري لدى نايكي','points':['نايكي اعتمدت على موديلات قديمة ناجحة، بينما المنافسين جذبوا المشترين بمنتجات جديدة.','محللون ربطوا ضعف التجديد بزيادة العروض والتخفيضات.','الحين تراهن على أحذية الجري والرياضة؛ مبيعات هذا الجانب تتحسن، لكنها ما عوّضت تراجع بقية أعمالها حتى الآن.']}]
for i,c in enumerate(cards):
 im=Image.new('RGB',(1080,1920),bg);d=ImageDraw.Draw(im)
 im.paste(Image.open(B/'logo.png').resize((128,128)),(82,126))
 d.rectangle((858,156,990,166),fill=green)
 def text(x,y,t,f,col=navy):d.text((x,y),t,font=f,fill=col,anchor='rt',direction='rtl')
 text(990,196,'ملخص تنفيذي • قصة',font(30,True),green)
 text(990,261,['١ من ٢','٢ من ٢'][i],font(28))
 for j,line in enumerate(c['title']):
  assert d.textlength(line,font=font(59,True),direction='rtl')<930
  text(990,331+j*85,line,font(59,True),red)
 source=Image.open(P/c['photo']).convert('RGB')
 if i==0: source=source.crop((440,335,1430,790))
 ph=ImageOps.pad(source,(916,420),color='#101115') if i==1 else ImageOps.fit(source,(916,420))
 mask=Image.new('L',ph.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,916,420),radius=28,fill=255);im.paste(ph,(82,530),mask)
 text(996,975,c['caption'],font(25),'#716E69')
 y=1050
 for p in c['points']:
  ls=[];line=''
  for w in p.split():
   t=(line+' '+w).strip()
   if d.textlength(t,font=font(48),direction='rtl')>852:ls.append(line);line=w
   else:line=t
  ls.append(line)
  d.ellipse((974,y+17,990,y+33),fill=green)
  for l in ls:text(949,y,l,font(48));y+=66
  y+=25
 assert y<1660,(i,y)
 if i==1:
  d.rounded_rectangle((82,1680,998,1788),radius=26,fill='#DFE7DF')
  text(876,1711,'شاركها مع صديقك اللي يحب نايكي',font(36,True),green)
  d.line([(922,1755),(924,1732),(938,1718),(957,1715),(957,1700),(980,1723),(956,1746),(957,1732),(941,1735),(922,1755)],fill=green,width=4,joint='curve')
 im.paste(Image.open(B/'logo.png').resize((78,78)),(501,1810))
 im.save(P/f'card-{i:02}.jpg',quality=95)
 im.resize((432,768)).save(P/f'preview-{i}.png')
 print(i,y)
(P/'copy.json').write_text(json.dumps(cards,ensure_ascii=False,indent=2))
