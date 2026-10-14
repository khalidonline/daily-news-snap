from pathlib import Path
import json,hashlib,math
from PIL import Image,ImageDraw,ImageFont,ImageOps
P=Path(__file__).parent
BG='#eeeae2';NAVY='#15394e';RED='#aa263a';GREEN='#174b38'
CTA='شاركها مع صديقك اللي تعجبه هذي المعلومة'
def font(n,b=False):return ImageFont.truetype('fonts/Almarai-'+('Bold' if b else 'Regular')+'.ttf',n)
def lines(draw,text,n,b,width):
 out=[];line=''
 for word in text.split():
  t=(line+' '+word).strip()
  if draw.textlength(t,font=font(n,b),direction='rtl')>width:out.append(line);line=word
  else:line=t
 if line:out.append(line)
 return out
for c in json.loads((P/'copy.json').read_text())['cards']:
 im=Image.new('RGB',(1080,1920),BG);d=ImageDraw.Draw(im)
 def badge(x,y,size):
  pic=Image.open('images/brand/badge.png').convert('RGB').resize((size,size));mask=Image.new('L',(size,size));ImageDraw.Draw(mask).ellipse((0,0,size-1,size-1),fill=255);im.paste(pic,(x,y),mask)
 def text(t,y,n=50,b=False,color=NAVY,x=998):
  d.text((x,y),t,font=font(n,b),fill=color,anchor='rt',direction='rtl',language='ar')
 def block(t,y,n=50,b=False,width=862,x=960,color=NAVY,maxlines=2):
  ls=lines(d,t,n,b,width);assert len(ls)<=maxlines,(c['key'],t,ls)
  for i,s in enumerate(ls):text(s,y+i*math.ceil(n*1.3),n,b,color,x)
  return {'text':t,'size':n,'box':[x-width,y,x,y+len(ls)*math.ceil(n*1.3)]}
 badge(82,156,100);d.rectangle((881,170,998,181),fill=GREEN);text('ملخص تنفيذي',205,31,True,GREEN)
 text('٦ أكتوبر ٢٠٢٦',260,27,color='#817d75')
 title=block(c['title'],324,54,True,916,998,RED,1)
 photo=c['photo'] if c['key']=='google' else 'pipeline-photo.jpeg'
 pic=ImageOps.fit(Image.open(P/photo).convert('RGB'),(916,480),centering=(0.5,0.88 if c['key']=='pipeline' else 0.5))
 mask=Image.new('L',pic.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,479),26,fill=255);im.paste(pic,(82,430),mask)
 text(c['caption'],930,28,color='#817d75')
 y=1000;bullets=[]
 for t in c['bullets']:
  d.ellipse((984,y+17,996,y+29),fill=GREEN)
  z=block(t,y);bullets.append(z);y=z['box'][3]+30
 closing=block(c['closing'],y+8,48,True,916,998,RED,2)
 cy=closing['box'][3]+56
 d.rounded_rectangle((82,cy,998,cy+106),radius=22,fill='#efdee0')
 ct=block(CTA,cy+28,38,True,795,897,RED,1)
 d.line([(926,cy+70),(930,cy+46),(945,cy+34),(962,cy+32),(962,cy+19),(988,cy+43),(962,cy+67),(962,cy+52),(946,cy+54),(926,cy+70)],fill=RED,width=5,joint='curve')
 badge(510,cy+141,60);assert cy+201<1850,(c['key'],cy)
 out=P/c['key'];out.mkdir(exist_ok=True)
 im.save(out/'card-00.jpg',quality=95,subsampling=0)
 im.resize((390,693),Image.Resampling.LANCZOS).save(out/'preview.jpg',quality=95)
 card={'sha256':hashlib.sha256((out/'card-00.jpg').read_bytes()).hexdigest(),'headline':title,'bullets':bullets,'cta':ct}
 (out/'readability.json').write_text(json.dumps({'version':1,'visual_review':{'approved':False,'reference':''},'cards':[card],'closing_measurement':closing},ensure_ascii=False,indent=2))
 (out/'copy.json').write_text(json.dumps(c,ensure_ascii=False,indent=2))
 print(c['key'],'body50 CTA38 title54', 'lines',[len(lines(d,t,50,False,862)) for t in c['bullets']],'bottom',cy+201)
