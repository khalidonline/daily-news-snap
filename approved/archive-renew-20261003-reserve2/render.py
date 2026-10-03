from PIL import Image,ImageDraw,ImageFont,ImageOps
from pathlib import Path
import json
P=Path(__file__).parent; B=P.parent/'berlin-design'
font=lambda n,b=False:ImageFont.truetype(str(B/('Almarai-Bold.ttf' if b else 'Almarai-Regular.ttf')),n)
navy='#143B56';red='#AB263A';green='#245741';bg='#EEEAE2'
sets=json.loads((P/'content.json').read_text())
for name,package in sets.items():
 cards=package["cards"]
 for i,c in enumerate(cards):
  im=Image.new('RGB',(1080,1920),bg);d=ImageDraw.Draw(im)
  im.paste(Image.open(B/'logo.png').resize((128,128)),(82,126))
  def text(x,y,t,f,col=navy):d.text((x,y),t,font=f,fill=col,anchor='rt',direction='rtl')
  d.rectangle((858,156,990,166),fill=green);text(990,196,'ملخص تنفيذي • قصة',font(30,True),green)
  text(990,261,['١ من ٢','٢ من ٢'][i],font(28))
  for j,line in enumerate(c['title']):
   assert d.textlength(line,font=font(62,True),direction='rtl')<925
   text(990,332+j*84,line,font(62,True),red)
  ph=Image.open(c['photo']).crop(c['crop'])
  ph=ImageOps.pad(ph,(916,420),color=bg) if c.get('pad') else ImageOps.fit(ph,(916,420))
  mask=Image.new('L',ph.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,916,420),radius=28,fill=255);im.paste(ph,(82,530),mask)
  text(996,975,c['caption'],font(24),'#716E69')
  y=1050
  for p in c['points']:
   ls=[];line=''
   for w in p.split():
    t=(line+' '+w).strip()
    if d.textlength(t,font=font(48),direction='rtl')>852:ls.append(line);line=w
    else:line=t
   ls.append(line);d.ellipse((974,y+17,990,y+33),fill=green)
   for l in ls:text(949,y,l,font(48));y+=66
   y+=25
  assert y<1660,(name,i,y)
  if c.get('share'):
   assert d.textlength(c['share'],font=font(36,True),direction='rtl')<780,(name,'CTA too long')
   d.rounded_rectangle((82,1680,998,1788),radius=26,fill='#DFE7DF');text(876,1711,c['share'],font(36,True),green)
   d.line([(922,1755),(924,1732),(938,1718),(957,1715),(957,1700),(980,1723),(956,1746),(957,1732),(941,1735),(922,1755)],fill=green,width=4,joint='curve')
  im.paste(Image.open(B/'logo.png').resize((78,78)),(501,1810))
  im.save(P/f'{name}-{i+1:02}.jpg',quality=95);im.resize((432,768)).save(P/f'{name}-preview-{i+1}.png')
  print(name,i,y)
(P/'rendered-copy.json').write_text(json.dumps({'status':'DRAFT_REVIEW_NOT_ARCHIVE_APPROVED','cards':sets},ensure_ascii=False,indent=2))
