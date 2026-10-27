from pathlib import Path
import hashlib
import json
from PIL import Image
from publishing_v2.fixed_information_template import render

OUT=Path(__file__).parent
source=OUT/'source-approved.png'
original=Image.open(source).convert('RGB')
text={
 'headline':'أكسفورد للمشاة… مو ليوم واحد!',
 'bullets':[
  'من ٢٦ أكتوبر، جزء من أكسفورد صار للمشاة؛ يبون الناس تتمشى وتتسوق براحتها.',
  'العام قفلوه ليوم واحد. هالمرة قفلوه بشكل دائم، وتجهيز الشارع بيكمل على مراحل.',
  'وفي ١٩٠٩، سيلفريدجز عرض أول طيارة عبرت المانش في ٣٧ دقيقة… وكان إنجاز وقتها!',
  'عرض الطيارة جاب ١٥٠ ألف زائر للمتجر خلال أربعة أيام!'],
 'closing':'أول جابوا طيارة علشان الناس تجي… والحين شالوا السيارات علشان تتمشى!',
 'captions':['طيارة بليريو داخل المتجر — ١٩٠٩','سيلفريدجز في شارع أكسفورد']}
im,blocks=render(text['headline'],text['bullets'],text['closing'],
                [original.crop((43,385,559,820)),original.crop((573,385,1037,820))],text['captions'],
                share_icon=original.crop((900,1620,1000,1707)))
target=OUT/'Oxford-Template-Preview.png';im.save(target)
report={'status':'PREVIEW_REQUIRES_OWNER_APPROVAL','published':False,
        'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'dimensions':list(im.size),'blocks':blocks,
        'font_candidate':'Owner-approved Almarai Bold 44px for all bullet paragraphs',
        'font_sha256':hashlib.sha256(Path('fonts/Almarai-Bold.ttf').read_bytes()).hexdigest(),
        'changes':'Approved edited text; 44px Bold bullets right aligned; original sharing arrow; unchanged photos and palette.',
        'sources':['https://www.oxfordstreetdc.org.uk/press/oxford-street-goes-traffic-free/',
                   'https://tfl.gov.uk/modes/driving/os-rules-and-exemptions',
                   'https://londonist.com/2016/01/secrets-of-selfridges']}
(OUT/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'path':str(target),'lines':[b['line_count'] for b in blocks if b['role']=='bullet']}))
