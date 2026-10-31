from pathlib import Path
import pytest
from PIL import Image, ImageOps, ImageChops


def test_information_layout_uses_expanded_body_and_pinned_branding():
    from publishing_v2.fixed_information_template import render
    copy = 'من ٢٦ أكتوبر، جزء من أكسفورد صار للمشاة؛ يبون الناس تتمشى وتتسوق براحتها.'
    image, blocks = render('عنوان', [copy]*4, 'النهاية',
        [Image.new('RGB',(500,500),'gray')]*2, ['صورة','صورة'])
    headline = next(b for b in blocks if b['role']=='headline')
    assert headline['box'][1] == 215
    assert abs(headline['line_boxes'][0][2]-1020) <= 1
    bullets = [b for b in blocks if b['role']=='bullet']
    gaps = ([bullets[0]['box'][1]-735] +
            [b['box'][1]-a['box'][3] for a,b in zip(bullets,bullets[1:])] +
            [1575-bullets[-1]['box'][3]])
    assert min(gaps) >= 20
    assert max(gaps)-min(gaps) <= 1
    assert all(b['line_boxes'][1][1]-b['line_boxes'][0][3] == 24 for b in bullets)
    assert all(b['line_count']==2 for b in bullets)
    assert all(b['box'][1]-a['box'][3]>=20 for a,b in zip(bullets,bullets[1:]))
    closing = next(b for b in blocks if b['role']=='closing')
    assert closing['box'][1] == 1575
    assert closing['box'][3] <= 1640
    assert image.getpixel((300,355)) == (128,128,128)
    reference = Image.open('approved/oxford-20261027/card.png').convert('RGB')
    header = reference.crop((760,110,1020,230))
    ink = ImageChops.difference(header, Image.new('RGB',header.size,(247,247,235))).getbbox()
    header = ImageOps.contain(header.crop(ink),(95,95),method=Image.Resampling.LANCZOS)
    x,y = 1020-header.width,115+(95-header.height)//2
    assert image.crop((x,y,x+header.width,y+header.height)).tobytes() == header.tobytes()
    arrow = ImageOps.contain(reference.crop((910,1630,1010,1717)),(75,65),method=Image.Resampling.LANCZOS)
    assert image.crop((1020-arrow.width,1665,1020,1665+arrow.height)).tobytes() == arrow.tobytes()


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
    from publishing_v2.fixed_information_template import render
    _, blocks = render('عنوان',
        ['من ٢٦ أكتوبر، جزء من أكسفورد صار للمشاة؛ يبون الناس تتمشى وتتسوق براحتها.'],
        'النهاية', [Image.new('RGB',(500,500),'gray')], ['صورة'])
    _information_geometry(blocks, settings)
    bullet = next(b for b in blocks if b['role']=='bullet')
    bullet['line_boxes'][1][1] -= 1
    bullet['line_boxes'][1][3] -= 1
    bullet['box'][3] -= 1
    with pytest.raises(BundleError, match='unequal visible line gaps'):
        _information_geometry(blocks,settings)


@pytest.mark.parametrize('style', [(46,'Regular'), (45,'Regular'), (45,'Bold')])
def test_retired_comparison_styles_cannot_override_approved_body(style):
    from publishing_v2.fixed_information_template import render
    from publishing_v2.bundle_api import BundleError
    with pytest.raises(BundleError, match='font changed'):
        render('عنوان',['نقطة قصيرة'],'النهاية',
            [Image.new('RGB',(500,500),'gray')],['صورة'], bullet_styles=[style])


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
    assert (12,95,70) in set(image.crop((925,115,1020,210)).getdata())
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
