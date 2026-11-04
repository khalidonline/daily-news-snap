import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
from publishing_v2.fixed_information_template import render
from publishing_v2.information_text_fit import prepare_text

p = Path('approved/us-results-20261104')
copy = {
    'headline': 'ترامب باقي… بس حزبه خسر الأغلبية!',
    'bullets': [
        'ترامب جمهوري، وحزبه كان ماسك الكونغرس: مجلس النواب ومجلس الشيوخ.',
        'تقديرات ٤ نوفمبر تعطي الأغلبية للديمقراطيين بالمجلسين؛ والفرز باقي.',
        'طيب ترامب يطلع؟ لا، هذي مو انتخابات رئاسة. هو باقي رئيس أمريكا.',
        'بس تمرير قوانينه بيحتاج تفاوض أكثر، والرقابة على إدارته بتزيد.'
    ],
    'closing': 'الكرسي باقي لترامب… بس مو كل اللي يبيه بيمشي!'
}
fit = prepare_text(copy)
assert fit['fit'], fit
for name, data in [('copy.json', copy), ('text-fit.json', fit)]:
    (p/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
photo = Image.open('approved/us-midterms-20261101/capitol.jpg')
photo = photo.crop((round(photo.width*.35), 0, round(photo.width*.82), round(photo.width*.47*350/468)))
trump = ImageOps.pad(Image.open(p/'trump.jpg'), (468,350), color='#F7F7EB')
im, blocks = render(copy['headline'], copy['bullets'], copy['closing'], [photo, trump],
                    ['الكونغرس — AOC', 'ترامب — الحزب الجمهوري'])
im.save(p/'card.png')
(p/'blocks.json').write_text(json.dumps(blocks, ensure_ascii=False, indent=2)+'\n')
for dest in ['story','saved-story']:
    overlay = im.resize((390,693))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0,0,389,39), fill='#222222')
    draw.rectangle((0,625,389,692), fill='#222222')
    overlay.save(p/(dest+'-review.png'))
print('FIT', fit['fit'], 'DIMENSIONS', im.size)
