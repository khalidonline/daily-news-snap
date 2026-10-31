from PIL import Image,ImageDraw,ImageFont,ImageOps
from pathlib import Path
import subprocess,math,json
geometry={}
blocks=[]
R=Path('.');P=R/'approved/lego-titanic-20261031';P.mkdir(exist_ok=True);old=R/'approved/tourism-cafes-20261030'
bg='#F7F7EB';blue='#0B3656';green='#0C5F46';red='#B60E32'
ref=Image.open(old/'source.png').convert('RGB');base=Image.new('RGB',(1080,1920),bg)
base.paste(ref.crop((760,110,1020,230)),(760,110));base.paste(ref.crop((60,1630,1020,1730)),(60,1630))
fonts={s:ImageFont.truetype(str(R/'fonts/Almarai-Bold.ttf'),s) for s in range(28,105)}
def text(im,txt,s,c,x,y):
 d=ImageDraw.Draw(im);b=list(d.textbbox((x,y),txt,font=fonts[s],anchor='mm',direction='rtl'));d.text((x,y),txt,font=fonts[s],fill=c,anchor='mm',direction='rtl')
 role={285:'headline',390:'question',958:'caption',1105:'option',1280:'answer',1410:'countdown',1390:'answer'}[y]
 row=dict(role=role,box=[b[0]-2,b[1]-2,b[2]+2,b[3]+2],color=c,line_count=1,font_size=s,line_boxes=[b])
 if role=='option' and c==bg:row['filled_correct_option']=True
 if role=='answer' and c==green:row['answer_reveal']=True
 blocks.append(row)
def logo(im,x,y,s):
 a=Image.open(R/'images/brand/badge.png').convert('RGB').resize((s,s),Image.Resampling.LANCZOS);m=Image.new('L',(s,s));ImageDraw.Draw(m).ellipse((0,0,s-1,s-1),fill=255);im.paste(a,(x,y),m)
logo(base,85,110,115)
photos=[Image.open(P/(n+'.jpg')).convert('RGB') for n in ['build','full']]
mask=Image.new('L',(456,410));ImageDraw.Draw(mask).rounded_rectangle((0,0,455,409),radius=28,fill=255)
audio=R/'approved/wheels-video-20261025/owner-approved-audio.m4a'
cmd=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1080x1920','-r','30','-i','-','-i',str(audio),'-t','12','-c:v','libx264','-pix_fmt','yuv444p','-crf','15','-preset','fast','-c:a','copy','-movflags','+faststart',str(P/'challenge.mp4')]
proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
for i in range(360):
 t=i/30;im=base.copy();d=ImageDraw.Draw(im);blocks=[]
 text(im,'توقع السعر',34,red,540,285);text(im,'كم تتوقع سعر هالليغو؟',64,green,540,390)
 for j,x in enumerate([72,552]):
  scale=1+.025*t/12;w=int(456*scale);h=int(410*scale)
  fit=ImageOps.contain(photos[j],(w,h),method=Image.Resampling.LANCZOS);a=Image.new('RGB',(w,h),'#FFFFFF');a.paste(fit,((w-fit.width)//2,(h-fit.height)//2));a=a.crop(((w-456)//2,(h-410)//2,(w-456)//2+456,(h-410)//2+410));im.paste(a,(x,505),mask)
 text(im,'وقت التركيب',32,'#7A7973',300,958);text(im,'تايتانيك — 10294',32,'#7A7973',780,958)
 for j,x in enumerate([90,570]):
  win=t>=8 and j==1
  d.rounded_rectangle((x,1040,x+420,1170),radius=20,fill=green if win else '#DBEFE6')
  text(im,['850 ريال','2550 ريال'][j],54,bg if win else blue,x+210,1105)
 if t<8:
  text(im,'اختر قبل كشف الإجابة',38,blue,540,1280)
  if t<3:logo(im,490,1360,100)
  else:
   phase=(t-3)%1;s=88+round(12*max(0,1-phase/.18));text(im,'54321'[int(t-3)],s,blue,540,1410)
 else:
  text(im,'حوالي 2550 ريال',54,green,540,1280)
  text(im,'679.99 دولار',42,blue,780,1390);text(im,'سعر أمريكي مرجعي',42,blue,300,1390)
  # Short reveal underline grows during the first quarter second.
  w=int(440*min(1,(t-8)/.25));d.rounded_rectangle((540-w//2,1460,540+w//2,1466),radius=3,fill=green)
 blocks.append(json.loads((old/'design-review.json').read_text())['cards'][0]['frame_designs'][0]['blocks'][-1])
 if t in [.5,3.5,4.5,5.5,6.5,7.5,8.5,11.5]:geometry[str(t)]=blocks
 if i==0:im.save(P/'source.png')
 proc.stdin.write(im.tobytes())
proc.stdin.close();assert proc.wait()==0
for t in [.5,3.5,4.5,5.5,6.5,7.5,8.5,11.5]:
 subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(P/'challenge.mp4'),'-frames:v','1',str(P/f'frame-{t}.png')],check=True)
sheet=Image.new('RGB',(1080,960))
for i,t in enumerate([.5,3.5,4.5,5.5,6.5,7.5,8.5,11.5]):sheet.paste(Image.open(P/f'frame-{t}.png').resize((270,480)),((i%4)*270,(i//4)*480))
sheet.save(P/'review.png')

(P/'geometry.json').write_text(json.dumps(geometry,ensure_ascii=False,indent=2))
