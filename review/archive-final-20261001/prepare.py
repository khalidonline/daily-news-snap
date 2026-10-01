import os,sys,json,hashlib,shutil,base64
from pathlib import Path
from PIL import Image
B=Path(__file__).resolve().parent; R=B.parent/'hybrid-work'
os.chdir(R);sys.path.insert(0,str(R));os.environ.update(THEME='light',FONT_FAMILY='Almarai')
from publishing_v2.approved_copy import render
digits=str.maketrans('0123456789','٠١٢٣٤٥٦٧٨٩')
out=B/'ready';out.mkdir(exist_ok=True)
def card(kind,title,body,punch,photo,caption=''):
 return dict(kind=kind,title=title,body=body,punch=punch,photo=str(photo),caption=caption)
def crop(package,name,box):
 p=B/'approved'/package/name;t=B/(package+'-'+name+'.photo.jpg')
 Image.open(p).crop(box).save(t,quality=98);return t
def build(name,cards):
 d=out/name;d.mkdir(exist_ok=True)
 for i,c in enumerate(cards):
  render(c,Path(c['photo']),d/f'card-{i:02}.jpg',f'{i} من {len(cards)-1}'.translate(digits) if i else '')
 (d/'copy.json').write_text(json.dumps(cards,ensure_ascii=False,indent=2))
 sheet=Image.new('RGB',(540*len(cards),960),'white')
 for i in range(len(cards)):sheet.paste(Image.open(d/f'card-{i:02}.jpg').resize((540,960)),(i*540,0))
 sheet.save(d/'contact.jpg')
 print(name,'rendered',len(cards))

# Only corrected public cards; source-only F35 card is deliberately excluded.
f='f35-20260920'
photos=[crop(f,'card-1.jpg',(96,490,984,980))]+[crop(f,f'card-{i}.jpg',(96,420,984,1060)) for i in (2,3,4)]
build(f,[
card('info','F-35… المعلومات قدّام عين الطيار','F-35 مقاتلة أمريكية مصممة عشان يصعب رصدها بالرادار. وخوذتها تعرض للطيار معلومات الطيران على زجاجها، قدّام عينه.','وقبل ما توصل لهالشكل… كان فيه سباق بين شركتين لبناء المقاتلة الجديدة.',photos[0],'الخوذة الحقيقية ورسم توضيحي لطريقة عرض البيانات'),
card('story','أسرع من الصوت… وتهبط عمودي','في يوليو ٢٠٠١، جمع النموذج التجريبي X-35B ثلاث قدرات في رحلة وحدة: أقلع من مسافة قصيرة، تجاوز سرعة الصوت، ثم هبط عمودي.\n\nكان هذا نموذج لوكهيد مارتن في المنافسة مع بوينغ.','التحدي كان يجمع سرعة المقاتلة مع هبوط ما يحتاج مدرج طويل.',photos[1],'النموذج التجريبي X-35B في المتحف'),
card('story','ثلاث جهات… وكل وحدة تبي شيء','القوات الجوية تحتاج مقاتلة تقلع من المدارج، والبحرية تحتاج نسخة لحاملات الطائرات. ومشاة البحرية يبون إقلاع قصير وهبوط عمودي.\n\nبوينغ اختبرت X-32، ولوكهيد مارتن اختبرت X-35.','كل فريق كان لازم يثبت فكرته بالطيران.',photos[2],'النموذج المنافس X-32B'),
card('story','فازت بالمنافسة… وبدأ تطوير المقاتلة','في أكتوبر ٢٠٠١، اختير فريق لوكهيد مارتن لتطوير المقاتلة الجديدة.\n\nالنموذج التجريبي ما كان المنتج النهائي؛ بعده بدأ تطوير نسخ F-35 الثلاث، وكل نسخة تخدم احتياج مختلف.','اختبار ناجح فتح الطريق… لكنه كان بداية رحلة التطوير.',photos[3],'F-35A — صورة أرشيفية')])

m='michelin-20260920';doc=json.loads((R/'docs/previews/2026-09-20-michelin.json').read_text())['cards']
ph=[crop(m,'card-1.jpg',(305,496,735,1190)),crop(m,'card-2.png',(325,421,751,1060)),crop(m,'card-3.png',(310,421,790,943))]
for i,c in enumerate(doc):c.update(photo=str(ph[i]),body=c['body'].translate(digits),caption='')
build(m,doc)

for name in ['apple-revision-20260926','silent-hill-revision-20260926']:
 doc=json.loads((R/'approved'/name/'spec.json').read_text())['cards']
 for i,c in enumerate(doc):c.update(photo=str(R/'approved'/name/f'source-{i:02}.jpg'),caption=c.get('image_caption') or '')
 build(name,doc)

doc=json.loads((B.parent/'disney-20260930/cards/copy.json').read_text())['cards']
# Latest user-edited information text retained, including the founder identification.
doc[0]['body']='ديزني اللي نعرفها بأفلامها وشخصياتها ومدن الألعاب، كان أول نجم كرتوني حقق لها نجاح كبير أرنب اسمه «أوزوالد».\n\nوالت ديزني هو والت ديزني، رسام ومنتج ورجل أعمال أمريكي، أسّس شركة ديزني وشارك في ابتكار شخصية ميكي ماوس.\n\nوالت وفريقه صنعوا أفلام أوزوالد، لكن حقوق الشخصية كانت عند شركة يونيفرسال.'
doc[0]['punch']='وعندما خسر والت حق الاستمرار في إنتاج أفلام أوزوالد، احتاج إلى ابتكار شخصية جديدة يملك حقوقها… ومن هنا جاء ميكي ماوس.'
for c in doc:c['photo']=str(B.parent/'disney-20260930/photos'/c['photo'])
build('disney-oswald-20260930',doc)

# Two connected cards replace four repetitive numerical frames.
d='7dogs-20260927';p=crop(d,'card-00.jpg',(96,440,984,1120))
build(d,[
card('info','تذكرة وحدة… جائزتها مليون ريال','في سبتمبر ٢٠٢٦، وصل «٧ دوجز» إلى مليون تذكرة في السينما السعودية، بحسب إعلان تركي آل الشيخ.\n\nومع الرقم كان فيه حافز مختلف: جائزة مليون ريال لصاحب التذكرة رقم مليون.','الفيلم احتاج قرابة أربعة أشهر عشان يوصل لهالرقم.',p,'مشهد من الفيلم'),
card('story','تصويره في الرياض… ومليون تذكرة بالسعودية','جمع الفيلم كريم عبدالعزيز وأحمد عز مع نجوم عرب وعالميين، وتصوّر بالكامل في الرياض. وبحسب الإعلان عن الإنتاج، تجاوزت ميزانيته ٤٠ مليون دولار.\n\nبدأ عرضه في مايو ٢٠٢٦. وفي ٢٢ سبتمبر وصلت مبيعاته بالسعودية إلى ٩٩٥ ألف تذكرة، وبعدها تجاوز المليون.','الرقم جاء بعد شهور من العرض… مو من أول أسبوع.',B/'7dogs-buggy.webp','كريم عبدالعزيز وأحمد عز — صورة ترويجية للفيلم')])

for name,source in [('air-rage-20261001',B.parent/'air-rage-20261001/cards'),('american-express-20260929',R/'approved/american-express-20260929'),('nespresso-20261001',B.parent/'nespresso-20261001/cards')]:
 d=out/name;d.mkdir(exist_ok=True)
 for i in range(4):shutil.copyfile(source/f'card-{i:02}.jpg',d/f'card-{i:02}.jpg')
 if name=='nespresso-20261001':shutil.copyfile(B.parent/'nespresso-20261001/revised/Nespresso-Card-03.jpg',d/'card-03.jpg')
print('All package files prepared')
