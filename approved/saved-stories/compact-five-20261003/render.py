"""Deterministic archive layout using approved originals; no network or paid API."""
import json,hashlib,shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
P=Path(__file__).parent
F=Path("fonts")
font=lambda n,b=False:ImageFont.truetype(str(F/("Almarai-Bold.ttf" if b else "Almarai-Regular.ttf")),n)
navy="#15394e";green="#174b38";red="#aa263a";ink="#263e4b";bg="#eeeae2"
review=[]
for pack in json.loads((P/"content.json").read_text()):
 out=P/pack["package"];out.mkdir(exist_ok=True)
 for i,c in enumerate(pack["cards"],1):
  im=Image.new("RGB",(1080,1920),bg);d=ImageDraw.Draw(im)
  def badge(x,y,n):
   ph=Image.open("images/brand/badge.png").convert("RGB").resize((n,n),Image.Resampling.LANCZOS)
   mask=Image.new("L",(n,n),0);ImageDraw.Draw(mask).ellipse((0,0,n-1,n-1),fill=255);im.paste(ph,(x,y),mask)
  badge(82,126,128)
  d.rounded_rectangle((858,156,990,166),radius=4,fill=green)
  def text(x,y,s,f,color=ink):
   d.text((x,y),s,font=f,fill=color,anchor="ra",direction="rtl",language="ar")
  text(988,195,"ملخص تنفيذي · قصة",font(30,True),green)
  text(988,260,"١ من ٢" if i==1 else "٢ من ٢",font(28),"#827e77")
  for j,line in enumerate(c["title"]):
   assert d.textlength(line,font=font(62,True),direction="rtl")<=916,(pack["package"],line)
   text(990,330+j*88,line,font(62,True),red)
  ph=Image.open(c["photo"]).convert("RGB")
  if c.get("crop"):ph=ph.crop(c["crop"])
  if pack["package"]=="apple-revision-20260926":
   ph=ImageOps.pad(ph,(916,420),color="white",centering=(.5,.5))
  else:ph=ImageOps.fit(ph,(916,420),centering=(.5,.5))
  mask=Image.new("L",ph.size,0);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,419),radius=30,fill=255)
  im.paste(ph,(82,540),mask)
  assert d.textlength(c["caption"],font=font(25),direction="rtl")<=916
  text(998,980,c["caption"],font(25),"#817d75")
  f=font(52);y=1060;line_counts=[]
  for point in c["points"]:
   lines=[];line=""
   for w in point.split():
    t=(line+" "+w).strip()
    if d.textlength(t,font=f,direction="rtl")>850:lines.append(line);line=w
    else:line=t
   if line:lines.append(line)
   assert len(lines)<=2,(pack["package"],i,point,lines)
   line_counts.append(len(lines))
   d.ellipse((972,y+20,990,y+38),fill=green)
   for j,l in enumerate(lines):text(944,y+j*72,l,f)
   y+=len(lines)*72+38
  assert y<1650,(pack["package"],i,y)
  if c.get("share"):
   d.rounded_rectangle((82,1656,998,1772),radius=28,fill="#efdee0")
   assert d.textlength(c["share"],font=font(36,True),direction="rtl")<770
   text(874,1687,c["share"],font(36,True),red)
   tile=Image.new("RGBA",(240,240),(0,0,0,0));td=ImageDraw.Draw(tile)
   td.rounded_rectangle((0,0,239,239),radius=54,fill=red)
   arrow=[(46,172),(49,132),(59,103),(80,80),(116,64),(116,29),(195,101),(116,168),(116,132),(91,134),(66,147),(46,172)]
   td.line(arrow,fill="white",width=10,joint="curve")
   tile=tile.resize((80,80),Image.Resampling.LANCZOS);im.paste(tile,(900,1674),tile)
  badge(501,1810,78)
  file=out/f"card-{i:02}.jpg";im.save(file,quality=96,subsampling=0)
  preview=im.resize((432,768),Image.Resampling.LANCZOS);preview.save(out/f"preview-{i:02}.png")
  review.append({"package":pack["package"],"card":i,"body_px":52,"line_counts":line_counts,"text_bottom":y,"sha256":hashlib.sha256(file.read_bytes()).hexdigest()})
(P/"layout-check.json").write_text(json.dumps(review,indent=2))
print(json.dumps(review,indent=2))
