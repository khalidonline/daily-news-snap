from pathlib import Path
import pytest
from PIL import Image


def test_information_layout_uses_expanded_body_and_pinned_branding():
    from publishing_v2.fixed_information_template import render
    copy = 'من ٢٦ أكتوبر، جزء من أكسفورد صار للمشاة؛ يبون الناس تتمشى وتتسوق براحتها.'
    image, blocks = render('عنوان', [copy]*4, 'النهاية',
        [Image.new('RGB',(500,500),'gray')]*2, ['صورة','صورة'])
    headline = next(b for b in blocks if b['role']=='headline')
    assert headline['box'][1] == 260
    assert abs(headline['line_boxes'][0][2]-1020) <= 1
    bullets = [b for b in blocks if b['role']=='bullet']
    assert bullets[0]['box'][1] == 855
    assert all(b['line_count']==2 for b in bullets)
    assert all(b['box'][1]-a['box'][3]>=20 for a,b in zip(bullets,bullets[1:]))
    closing = next(b for b in blocks if b['role']=='closing')
    assert closing['box'][1] == 1540
    assert closing['box'][3] <= 1605
    assert image.getpixel((300,355)) == (128,128,128)
    reference = Image.open('approved/oxford-20261027/card.png').convert('RGB')
    assert image.crop((760,110,1020,230)).tobytes() == reference.crop((760,110,1020,230)).tobytes()
    assert image.crop((910,1630,1010,1717)).tobytes() == reference.crop((910,1630,1010,1717)).tobytes()


def test_single_photo_supported_without_a_different_template():
    from publishing_v2.fixed_information_template import render
    image, blocks=render('عنوان',['نقطة'],'النهاية',
        [Image.new('RGB',(1000,500),'gray')],['الصورة'])
    assert image.getpixel((540,500)) == (128,128,128)
    assert len([b for b in blocks if b['role']=='caption'])==1


def test_information_gate_rejects_closing_outside_role_region():
    import json
    from publishing_v2.design_contract import _information_geometry
    from publishing_v2.bundle_api import BundleError
    settings=json.loads(Path('publishing_v2/design-settings.json').read_text())
    with pytest.raises(BundleError, match='region'):
        _information_geometry([{'role':'closing','box':[60,1500,1000,1550],'line_count':1}],settings)


def test_information_gate_rejects_insufficient_actual_gap():
    import json
    from publishing_v2.design_contract import _information_geometry
    from publishing_v2.bundle_api import BundleError
    settings=json.loads(Path('publishing_v2/design-settings.json').read_text())
    with pytest.raises(BundleError, match='gap'):
        _information_geometry([
            {'role':'bullet','box':[60,855,980,988],'line_count':2},
            {'role':'bullet','box':[60,1005,980,1125],'line_count':2}],settings)


def test_owner_four_style_comparison_uses_requested_faces_and_sizes():
    from publishing_v2.fixed_information_template import render
    _,blocks=render('عنوان',['نقطة قصيرة']*4,'النهاية',
        [Image.new('RGB',(500,500),'gray')]*2,['صورة','صورة'],
        bullet_styles=[(46,'Regular'),(45,'Regular'),(45,'Bold'),(44,'Bold')])
    bullets=[b for b in blocks if b['role']=='bullet']
    assert [(b['font_size'],b['font_weight']) for b in bullets]==[(46,'Regular'),(45,'Regular'),(45,'Bold'),(44,'Bold')]
    assert all(abs(b['line_boxes'][0][2]-980)<=1 for b in bullets)


def test_bullet_continuation_aligns_right_at_approved_44_bold():
    from publishing_v2.fixed_information_template import render
    _, blocks=render('عنوان',
        ['من ٢٦ أكتوبر، جزء من أكسفورد صار للمشاة؛ يبون الناس تتمشى وتتسوق براحتها.'],
        'النهاية', [Image.new('RGB',(500,500),'gray')]*2,['صورة','صورة'])
    bullet=next(b for b in blocks if b['role']=='bullet')
    assert bullet['font_size']==44
    assert bullet['font_weight']=='Bold'
    assert bullet['line_count']==2
    assert all(abs(b[2]-980)<=1 for b in bullet['line_boxes'])


def test_fixed_canvas_palette_and_no_overflow(tmp_path):
    from publishing_v2.fixed_information_template import render
    image, geometry = render('عنوان قصير', ['هذه سالفة قصيرة.']*4,
                             'وهنا نهاية السالفة!', [Image.new('RGB',(500,500),'gray')]*2,
                             ['الصورة الأولى','الصورة الثانية'])
    assert image.size == (1080,1920)
    assert image.getpixel((0,0)) == (247,247,235)
    assert image.getpixel((800,130)) == (12,95,70)
    assert all(b['box'][2] <= 1020 and b['box'][3] <= 1730 for b in geometry)
    assert all(b['line_count'] <= 2 for b in geometry)
    assert any(b['role']=='cta' for b in geometry)


def test_long_copy_is_rejected_not_shrunk_or_clipped():
    from publishing_v2.fixed_information_template import render
    with pytest.raises(ValueError,match='overflow'):
        render('عنوان', ['كلام طويل '*80], 'النهاية',
               [Image.new('RGB',(500,500),'gray')]*2,['صورة','صورة'])


def test_real_arabic_two_lines_pass_without_mistaking_dots_for_lines():
    import json
    from publishing_v2.fixed_information_template import render
    from publishing_v2.design_contract import _pixels
    image,blocks=render('عنوان قصير',
        ['من ٢٦ أكتوبر، جزء من أكسفورد صار للمشاة؛ يبون الناس تتمشى وتتسوق براحتها.'],
        'وهنا نهاية السالفة!', [Image.new('RGB',(500,500),'gray')]*2,['صورة','صورة'])
    _pixels(image,blocks,json.loads(Path('publishing_v2/design-settings.json').read_text()))
    from publishing_v2.bundle_api import BundleError
    bullet=next(b for b in blocks if b['role']=='bullet')
    bullet['line_boxes'].append(bullet['line_boxes'][-1]);bullet['line_count']=3
    with pytest.raises(BundleError):
        _pixels(image,blocks,json.loads(Path('publishing_v2/design-settings.json').read_text()))
