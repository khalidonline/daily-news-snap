from PIL import Image,ImageDraw,ImageFont,ImageOps
from pathlib import Path
import json,subprocess,hashlib
P=Path('approved/tourism-cablecar-20261028'); bg='#F7F7EB'; blue='#0B3656'; green='#0C5F46'; red='#B60E32'
ref=Image.open('approved/tourism-hotel-revised-20261028/source.png').convert('RGB')
base=Image.new('RGB',(1080,1920),bg)
base.paste(ref.crop((760,110,1020,230)),(760,110));base.paste(ref.crop((60,1630,1020,1730)),(60,1630))
def logo(im,xy,size):
 a=Image.open('images/brand/badge.png').convert('RGB').resize((size,size),Image.Resampling.LANCZOS);m=Image.new('L',(size,size));ImageDraw.Draw(m).ellipse((0,0,size-1,size-1),fill=255);im.paste(a,xy,m)
logo(base,(85,110),115)
for name,x,c in [('ngong-ping',60,(.34,.5)),('hon-thom',552,(.51,.5))]:
 a=ImageOps.fit(Image.open(P/(name+'.jpg')),(468,540),method=Image.Resampling.LANCZOS,centering=c);m=Image.new('L',a.size);ImageDraw.Draw(m).rounded_rectangle((0,0,467,539),radius=30,fill=255);base.paste(a,(x,390),m)
allblocks={}
for t in range(12):
 im=base.copy();d=ImageDraw.Draw(im);blocks=[]
 def txt(role,text,size,c,x,y):
  f=ImageFont.truetype('fonts/Almarai-Regular.ttf',size);b=list(d.textbbox((x,y),text,font=f,anchor='mm',direction='rtl'));d.text((x,y),text,font=f,fill=c,anchor='mm',direction='rtl');blocks.append(dict(role=role,box=[b[0]-4,b[1]-4,b[2]+4,b[3]+4],color=c,line_count=1,font_size=size,line_boxes=[b]))
 txt('headline','أيها أطول؟',52,red,540,310)
 txt('caption','نغونغ بينغ — هونغ كونغ',28,'#7A7973',294,971)
 txt('caption','هون ثوم — فيتنام',28,'#7A7973',786,971)
 txt('question','أي رحلة تلفريك مسارها أطول؟',48,green,540,1100)
 for x in (90,570): d.rounded_rectangle((x,1240,x+420,1340),radius=25,fill='#DBEFE6',outline=green if t>=8 and x==570 else None,width=4)
 txt('option','نغونغ بينغ',44,blue,300,1290);txt('option','هون ثوم',44,blue,780,1290)
 if t<8:txt('answer','اختر قبل كشف الإجابة',36,blue,540,1410)
 else:
  txt('answer','هون ثوم: نحو ٧٫٩ كم',38,blue,540,1410)
  txt('answer','مقابل ٥٫٧ كم لنغونغ بينغ',38,blue,540,1490)
 if t<3:logo(im,(495,1485),90)
 elif t<8:txt('countdown','٥٤٣٢١'[t-3],72,blue,540,1530)
 # CTA inherited exactly from complete approved source; geometry inherited.
 blocks.append(json.loads(Path('approved/tourism-hotel-revised-20261028/design-review.json').read_text())['cards'][0]['frame_designs'][0]['blocks'][-1])
 im.save(P/f'state-{t:02}.png');allblocks[t]=blocks
 if t==0:im.save(P/'source.png')
(P/'geometry.json').write_text(json.dumps(allblocks,ensure_ascii=False,indent=2))
subprocess.run(['ffmpeg','-v','error','-y','-framerate','1','-i',str(P/'state-%02d.png'),'-i','approved/wheels-video-20261025/owner-approved-audio.m4a','-t','12','-r','30','-c:v','libx264','-pix_fmt','yuv444p','-crf','12','-preset','fast','-c:a','copy','-movflags','+faststart',str(P/'challenge.mp4')],check=True)
for t in [.5,3.5,4.5,5.5,6.5,7.5,8.5,11.5]:
 subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(P/'challenge.mp4'),'-frames:v','1',str(P/f'frame-{t}.png')],check=True)
ims=[Image.open(P/f'frame-{t}.png').resize((270,480)) for t in [.5,3.5,4.5,5.5,6.5,7.5,8.5,11.5]]
sheet=Image.new('RGB',(1080,960));[sheet.paste(a,((i%4)*270,(i//4)*480)) for i,a in enumerate(ims)];sheet.save('/tmp/cable-review.png')
