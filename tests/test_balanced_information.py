import copy
import json
from pathlib import Path
import pytest
from PIL import Image
from publishing_v2.fixed_information_template import render
from publishing_v2.design_contract import _information_geometry, _pixels

TEXTS = [
    'اليوم ٣١ أكتوبر، الهالوين. والقرع اللي نشوفه مع هالمناسبة، ترى مو هو بداية السالفة.',
    'في إيرلندا، كانوا يفرغون اللفت ويحفرون فيه وجيه تخوف، ويحطون داخله شمعة.',
    'يوم هاجروا لأمريكا، لقوا القرع أوفر وأسهل بالحفر، فصاروا يستخدمونه بدال اللفت.',
    'ومع الوقت، اشتهر القرع وصار مرتبط بالهالوين… واللفت اللي بدأت منه السالفة، محد يجيبه بطاري!'
]

def sample():
    return render('الهالوين… سالفة القرع بدأت بلفتة!', TEXTS,
                  'الشهرة راحت للقرع… والبداية كانت لفتة!',
                  [Image.new('RGB',(960,350),'#888888')], ['اللفت والقرع'])

def test_real_export_has_equal_ink_gaps_and_keeps_approved_title():
    image, blocks = sample()
    assert image.size == (1080,1920)
    bullets=[b for b in blocks if b['role']=='bullet']
    assert [b['text'] for b in bullets]==TEXTS
    for b in bullets:
        assert b['font_size']==44 and b['font_weight']=='Bold'
        assert b['line_count']==2
        a,z=b['line_boxes']
        assert z[1]-a[3]==24
        # Detect dishonest metadata: actual colored pixels fill measured ink boxes.
        for x1,y1,x2,y2 in b['line_boxes']:
            crop=image.crop((x1,y1,x2,y2))
            assert any(p!=(247,247,235) for p in crop.crop((0,0,crop.width,1)).get_flattened_data())
    gaps=[bullets[0]['box'][1]-735]+[b['box'][1]-a['box'][3] for a,b in zip(bullets,bullets[1:])]+[1575-bullets[-1]['box'][3]]
    assert gaps==[64,64,65,64,64]
    settings=json.loads(Path('publishing_v2/design-settings.json').read_text())
    _pixels(image,blocks,settings)

def test_gate_rejects_unequal_paragraph_distribution():
    _, blocks=sample()
    broken=copy.deepcopy(blocks)
    bullet=next(b for b in broken if b['role']=='bullet')
    bullet['box'][1]+=3
    settings=json.loads(Path('publishing_v2/design-settings.json').read_text())
    with pytest.raises(Exception):
        _information_geometry(broken,settings)

def test_overlong_copy_is_rejected_not_shrunk():
    with pytest.raises(ValueError,match='overflow'):
        render('عنوان', ['كلمة طويلة '*100], 'القفلة', [Image.new('RGB',(960,350))], ['صورة'])

def test_header_uses_box_width_without_scaling_empty_source_margins():
    image,_=sample()
    points=[(x,y) for y in range(115,210) for x in range(925,1020)
            if image.getpixel((x,y))==(12,95,70)]
    assert points
    assert max(x for x,y in points)-min(x for x,y in points)+1>=90

def test_three_photos_have_separate_centered_captions():
    image,blocks=render('عنوان',TEXTS,'القفلة',
                       [Image.new('RGB',(304,350),'gray')]*3,
                       ['فانوس القرع','القرع','اللفت'])
    captions=[b for b in blocks if b['role']=='caption']
    assert len(captions)==3
    assert [b['text'] for b in captions]==['فانوس القرع','القرع','اللفت']
    for b,center in zip(captions,[212,540,868]):
        assert abs((b['box'][0]+b['box'][2])/2-center)<=1
    _pixels(image,blocks,json.loads(Path('publishing_v2/design-settings.json').read_text()))
