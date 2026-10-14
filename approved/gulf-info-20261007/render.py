from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import json,base64,hashlib
ROOT=Path.cwd(); P=Path(__file__).parent; C=P.parent/'gulf-challenge-20261007'
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
def cta(im,s,y):
 d=ImageDraw.Draw(im);d.rounded_rectangle((82,y,998,y+120),23,fill='#efdee0')
 txt(im,y+13,'شاركها مع صديقك',38,True,RED,878)
 txt(im,y+64,'اللي تعجبه هذي المعلومة',38,True,RED,878)
 d.line([(913,y+67),(918,y+42),(933,y+29),(951,y+27),(951,y+16),(975,y+38),(951,y+61),(951,y+46),(934,y+49),(913,y+67)],fill=RED,width=5,joint='curve')
 badge(im,512,y+145,56)
def save(im,p):
 im.save(p/'card-00.jpg',quality=94,subsampling=0)
 im.resize((540,960)).save(p/'preview.jpg',quality=94)
 (p/'card-00.jpg.b64').write_text(base64.b64encode((p/'card-00.jpg').read_bytes()).decode())
im=canvas();headline='أمس أخذنا الخليج… وكررنا إنجاز قبل ٥٢ سنة';n=title(im,headline)
pic=ImageOps.fit(Image.open(P/'photo.png').convert('RGB'),(916,516))
m=Image.new('L',pic.size);ImageDraw.Draw(m).rounded_rectangle((0,0,915,515),28,fill=255);im.paste(pic,(82,398),m)
txt(im,932,'المنتخب السعودي — صورة أرشيفية',25,color='#817d75')
lines=[['الأخضر فاز على الإمارات ٢–٠،','وحقق كأس الخليج للمرة الرابعة.'],['ثاني منتخب ياخذ الكأس بشباك نظيفة','ويفوز بكل مواجهاته، بعد الكويت ١٩٧٤.']]
y=1015
for paragraph in lines:
 ImageDraw.Draw(im).ellipse((980,y+17,992,y+29),fill=GREEN)
 for s in paragraph:txt(im,y,s,48,x=956);y+=72
 y+=38
txt(im,1403,'رجع كأس الخليج بعد غياب من ٢٠٠٤.',49,True,RED)
cta(im,'شاركها مع صديقك اللي تعجبه هذي المعلومة',1550);save(im,P)
(P/'copy.json').write_text(json.dumps({'headline':headline,'headline_font':n,'body_font':48,'bullets':lines,'closing':'رجع كأس الخليج بعد غياب من ٢٠٠٤.','cta':'شاركها مع صديقك اللي تعجبه هذي المعلومة'},ensure_ascii=False,indent=2))
im=canvas();title(im,'أمس الكأس للأخضر… واليوم التحدّي لك')
txt(im,406,'شعار واحد مختلف… وينه؟',51,False,GREEN)
crest=Image.open(C/'crest.png').convert('RGBA');crest.thumbnail((140,199),Image.Resampling.LANCZOS)
# Exact grid puzzle: original crest unchanged, one tile has a 12-degree orientation.
for row in range(4):
 for col in range(4):
  tile=Image.new('RGBA',(204,225));tile.alpha_composite(crest,((204-crest.width)//2,(225-crest.height)//2))
  if (row,col)==(2,2):tile=tile.rotate(12,resample=Image.Resampling.BICUBIC)
  im.paste(tile,(96+col*228,528+row*232),tile)
txt(im,1510,'لقيته؟ خلّ خويك يجرّب',43,True,GREEN)
cta(im,'شاركها مع صديقك اللي تعجبه هذي المعلومة',1600);save(im,C)
(C/'copy.json').write_text(json.dumps({'headline':'أمس الكأس للأخضر… واليوم التحدّي لك','prompt':'شعار واحد مختلف… وينه؟','answer_internal_only':'Third row from top, second column from right; crest rotated 12 degrees.','grid':[4,4],'different_tiles':1,'cta':'شاركها مع صديقك وتحدّه يلقاه'},ensure_ascii=False,indent=2))
for p,name in [(P,'photo.png'),(C,'crest.png')]:
 (p/(name+'.b64')).write_text(base64.b64encode((p/name).read_bytes()).decode())
print('RENDERED two one-card packages; headline',n,'body 48; answer kept internal')
