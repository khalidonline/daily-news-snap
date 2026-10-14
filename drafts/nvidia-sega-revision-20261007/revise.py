from PIL import Image,ImageDraw,ImageFont,ImageOps
from pathlib import Path
import json,hashlib
p=Path(__file__).parent
old=Image.open(p/'original.jpg').convert('RGB');im=old.copy();d=ImageDraw.Draw(im);bg=(238,234,226)
d.rectangle((60,415,1020,994),fill=bg)
photo=ImageOps.fit(Image.open(p/'riva-pd.jpg').convert('RGB'),(916,510),Image.Resampling.LANCZOS,centering=(.5,.55))
mask=Image.new('L',photo.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,915,509),30,fill=255);im.paste(photo,(82,430),mask)
f=ImageFont.truetype(str(p/'Almarai-Regular.ttf'),27)
d.text((990,950),'لقطة مقرّبة لمعالج RIVA 128 داخل كرت الشاشة',font=f,fill='#827f77',anchor='rt',direction='rtl',language='ar')
d.rectangle((0,1766,1079,1919),fill=bg)
badge=old.crop((82,148,176,242)).resize((56,56),Image.Resampling.LANCZOS)
im.paste(badge,(512,1790))
im.save(p/'NVIDIA-card-02-revised.png')
im.save(p/'NVIDIA-card-02-revised.jpg',quality=96,subsampling=0)
im.resize((540,960),Image.Resampling.LANCZOS).save(p/'preview.png')
# Verify all original headline/body/CTA pixels unchanged in lossless review file.
for box in [(0,0,1080,415),(0,995,1080,1766)]:
 assert im.crop(box).tobytes()==old.crop(box).tobytes()
meta={'status':'DRAFT_FOR_OWNER_REVIEW_NOT_PUBLISHED','replaces_card':2,'original_identity':'5e63a9e4f8edc7d3e71de8575429d6e46380cc2efc5a42ca992c74614010d6bc','changed':['photo','photo caption','footer rights links replaced by brand badge'],'unchanged':['headline','body','closing','CTA','font','card 1'],'image':{'source_url':'https://commons.wikimedia.org/wiki/File:RIVA_128_GPU.jpg','original_url':'https://upload.wikimedia.org/wikipedia/commons/8/85/RIVA_128_GPU.jpg','author':'Hyins','license':'Public domain','attribution_required':False,'description':'Actual RIVA 128 chip; photographer released worldwide with no conditions. Photo cropped/resized.'},'sha256':hashlib.sha256((p/'NVIDIA-card-02-revised.jpg').read_bytes()).hexdigest(),'paid_model_requests':0}
(p/'revision.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
print(meta['sha256'])
