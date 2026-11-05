"""Render the owner-approved copy through the unchanged master. No publishing."""
import json
from pathlib import Path
from PIL import Image, ImageDraw
from publishing_v2.fixed_information_template import render
from publishing_v2.information_text_fit import prepare_text

p = Path('approved/bonfire-night-20261105')
copy = {
    'headline': 'احتفال بريطانيا اليوم… وراه محاولة تفجير!',
    'bullets': [
        'اليوم ٥ نوفمبر، بريطانيا تحتفل بالألعاب النارية. والسالفة وراها مبنى البرلمان!',
        'عام ١٦٠٥، حطّوا تحته ٣٦ برميل بارود؛ ناوين يفجّرونه بالملك وأعضاء البرلمان.',
        'جاي فوكس، واحد من المجموعة، كان بيشعل البارود. بس مسكوه وفشلت خطتهم.',
        'ومن وقتها يحتفلون بفشلها. وللحين يفتشون تحت البرلمان قبل افتتاحه الرسمي!'
    ],
    'closing': 'محاولة فشلت… وصارت مناسبة لها أكثر من ٤٠٠ سنة!'
}
fit = prepare_text(copy)
assert fit['fit'], fit
for name, data in [('copy.json', copy), ('text-fit.json', fit)]:
    (p/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
photos = [Image.open(p/'bonfire.jpg'), Image.open(p/'parliament.jpg')]
im, blocks = render(copy['headline'], copy['bullets'], copy['closing'], photos,
                    ['احتفال سابق — ٢٠١٣', 'مبنى البرلمان وبيغ بن'])
im.save(p/'card.png')
(p/'blocks.json').write_text(json.dumps(blocks, ensure_ascii=False, indent=2)+'\n')
for dest in ['story', 'saved-story']:
    overlay = im.resize((390,693))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0,0,389,39), fill='#222222')
    draw.rectangle((0,625,389,692), fill='#222222')
    overlay.save(p/(dest+'-review.png'))
print('FIT', fit['fit'], 'DIMENSIONS', im.size)
