import os,sys,json,inspect
from pathlib import Path
from PIL import Image,ImageOps
B=Path(__file__).resolve().parent;R=B.parent/'hybrid-work';os.chdir(R);sys.path.insert(0,str(R));os.environ.update(THEME='light',FONT_FAMILY='Almarai')
import story_bot,news_bot
from publishing_v2.approved_copy import render
# Archive-only fit: retain the full reviewed photograph; never clip faces or documentary detail.
s=inspect.getsource(story_bot._render_frame)
a=s.index('            pw, ph = pic.size');z=s.index('            rounded =',a)
s=s[:a]+'''            fitted = ImageOps.contain(pic, (box_w, box_h), Image.Resampling.LANCZOS)
            pic = Image.new('RGB',(box_w,box_h),BG_TOP)
            pic.paste(fitted,((box_w-fitted.width)//2,(box_h-fitted.height)//2))
'''+s[z:]
story_bot.__dict__['ImageOps']=ImageOps;exec(s,story_bot.__dict__)
s=inspect.getsource(news_bot.render_story)
a=s.index('            pw, ph = photo.size');z=s.index('            rounded =',a)
s=s[:a]+'''            fitted = ImageOps.contain(photo, (box_w, box_h), Image.Resampling.LANCZOS)
            photo = Image.new('RGB',(box_w,box_h),BG_TOP)
            photo.paste(fitted,((box_w-fitted.width)//2,(box_h-fitted.height)//2))
'''+s[z:]
news_bot.__dict__['ImageOps']=ImageOps;exec(s,news_bot.__dict__)
for name in ['f35-20260920','michelin-20260920','7dogs-20260927']:
 d=B/'ready'/name;cards=json.loads((d/'copy.json').read_text())
 if name.startswith('f35'):
  orig=B/'approved'/name
  for i,c in enumerate(cards):
   p=B/f'fixed-f35-{i}.jpg'
   box=(96,490,545,955) if i==0 else (96,420,984,930)
   Image.open(orig/f'card-{i+1}.jpg').crop(box).save(p,quality=98);c['photo']=str(p)
  cards[0]['caption']='خوذة الطيار — صورة أرشيفية'
  cards[1],cards[2]=cards[2],cards[1]
 if name.startswith('7dogs'):
  p=B/'fixed-7dogs.jpg';Image.open(B/'approved'/name/'card-00.jpg').crop((96,440,984,990)).save(p,quality=98);cards[0]['photo']=str(p)
 for i,c in enumerate(cards):render(c,Path(c['photo']),d/f'card-{i:02}.jpg',f'{i} من {len(cards)-1}'.translate(str.maketrans('0123456789','٠١٢٣٤٥٦٧٨٩')) if i else '')
 (d/'copy.json').write_text(json.dumps(cards,ensure_ascii=False,indent=2))
 sheet=Image.new('RGB',(540*len(cards),960),'white')
 for i in range(len(cards)):sheet.paste(Image.open(d/f'card-{i:02}.jpg').resize((540,960)),(i*540,0))
 sheet.save(d/'contact.jpg')
 print(name)
