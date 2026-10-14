from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import base64
ROOT=Path.cwd();C=Path(__file__).parent
BG='#eeeae2'; NAVY='#15394e'; RED='#aa263a'; GREEN='#174b38'
def font(n,b=False): return ImageFont.truetype(str(ROOT/'fonts'/('Almarai-'+('Bold' if b else 'Regular')+'.ttf')),n)
def canvas():
 im=Image.new('RGB',(1080,1920),BG);d=ImageDraw.Draw(im)
 badge(im,82,150,94);d.rectangle((876,169,990,179),fill=GREEN)
 txt(im,200,'ملخص تنفيذي',30,True,GREEN)
 return im
def badge(im,x,y,n):
 b=Image.open(ROOT/'images/brand/badge.png').convert('RGB').resize((n,n));m=Image.new('L',(n,n));ImageDraw.Draw(m).ellipse((0,0,n-1,n-1),fill=255);im.paste(b,(x,y),m)
def txt(im,y,s,n=48,b=False,color=NAVY,x=992):
 d=ImageDraw.Draw(im);assert d.textlength(s,font=font(n,b),direction='rtl')<=920,(s,n)
 d.text((x,y),s,font=font(n,b),fill=color,anchor='rt',direction='rtl',language='ar')
def title(im,s):
 n=52
 while ImageDraw.Draw(im).textlength(s,font=font(n,True),direction='rtl')>916:n-=1
 assert n>=40
 txt(im,305,s,n,True,RED);return n
def save(im,p):
 im.save(p/'card-00.jpg',quality=94,subsampling=0)
 im.resize((540,960)).save(p/'preview.jpg',quality=94)
 (p/'card-00.jpg.b64').write_text(base64.b64encode((p/'card-00.jpg').read_bytes()).decode())
im=canvas();title(im,'أمس الكأس للأخضر… واليوم التحدّي لك')
txt(im,406,'شعار واحد مختلف… وينه؟',51,False,GREEN)
crest=Image.open(ROOT/'approved/gulf-challenge-20261007/crest.png').convert('RGBA');crest.thumbnail((140,199),Image.Resampling.LANCZOS)
# Exact grid puzzle: original crest unchanged, one tile has a 12-degree orientation.
for row in range(4):
 for col in range(4):
  tile=Image.new('RGBA',(204,225));tile.alpha_composite(crest,((204-crest.width)//2,(225-crest.height)//2))
  if (row,col)==(2,2):tile=tile.rotate(12,resample=Image.Resampling.BICUBIC)
  im.paste(tile,(96+col*228,528+row*232),tile)
y=1490
d=ImageDraw.Draw(im)
d.rounded_rectangle((82,y,998,y+110),23,fill='#efdee0')
txt(im,y+30,'لقيته؟ خلّ خويك يجرّب',43,True,RED,878)
d.line([(913,y+67),(918,y+42),(933,y+29),(951,y+27),(951,y+16),(975,y+38),(951,y+61),(951,y+46),(934,y+49),(913,y+67)],fill=RED,width=5,joint='curve')
badge(im,512,1745,56);save(im,C)
