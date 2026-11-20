"""Closed, immutable reference variants, not a general chart renderer.

Only the specifically reviewed exports and their complete semantic specs
are accepted. A changed/new design requires a new separately reviewed variant;
caller-provided hashes/paths cannot authorize it. Publication still requires
all existing source, approval, account, quota and idempotency checks.
"""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parents[1]
SPECS = {'pictogram-count-v1': {'variant': 'pictogram-count-v1',
                        'reference_sha256': '6c10247642fe38b6fc615a9fa88be579fcd19ce3727a578c510d09fe8150a021',
                        'title': 'كم ملعقة سكر في مشروبك؟',
                        'subtitle': 'في كل 250 مل من المشروب',
                        'unit': 'ملاعق صغيرة تقريبا',
                        'basis': {'quantity': 250, 'unit': 'ml'},
                        'note': '',
                        'rows': [{'label': 'ريد بول', 'count': 7},
                                 {'label': 'كوكاكولا', 'count': 7},
                                 {'label': 'برتقال معصور طازج', 'count': 5},
                                 {'label': 'كراميل ماكياتو من ستاربكس', 'count': 4}],
                        'pictogram': {'kind': 'teaspoon', 'capacity': 7, 'direction': 'rtl'},
                        'layout': {'canvas': [1080, 1920],
                                   'row_step': 286,
                                   'pictogram_y': [620, 906, 1192, 1478]}},
 'annotated-range-v1': {'variant': 'annotated-range-v1',
                        'reference_sha256': 'ae3f0e81f86231260e4052f33fc8abc3dfd05a04235da698de21003306080d1d',
                        'title': 'ساعة على جوالك كم تسحب من باقتك؟',
                        'subtitle': 'ساعة كاملة لكل تطبيق',
                        'unit': 'بالميقا تقريبا',
                        'basis': {'quantity': 1, 'unit': 'hour'},
                        'note': 'استهلاك الفيديو يتغير حسب الجودة والمقاطع.',
                        'rows': [{'label': 'تيك توك',
                                  'low': 500,
                                  'high': 1000,
                                  'usage': 'تصفح المقاطع'},
                                 {'label': 'سناب',
                                  'low': 360,
                                  'high': 1200,
                                  'usage': 'مقاطع الأضواء والستوري'},
                                 {'label': 'يوتيوب',
                                  'low': 240,
                                  'high': 500,
                                  'usage': 'الجودة التلقائية إذا اختارت 480p'},
                                 {'label': 'إكس',
                                  'low': 50,
                                  'high': 60,
                                  'usage': 'قراءة تغريدات بدون فيديو'},
                                 {'label': 'خرائط قوقل',
                                  'low': 30,
                                  'high': 50,
                                  'usage': 'تتبع الطريق'}],
                        'scale': {'min': 0, 'max': 1200, 'direction': 'rtl'},
                        'layout': {'canvas': [1080, 1920],
                                   'bar_axis': [80, 1005],
                                   'bar_y': [604, 807, 1010, 1213, 1416]}}}
FILES = {'pictogram-count-v1': 'sugar-pictogram.png', 'annotated-range-v1': 'mobile-data-ranges.png'}

SPECS['calories-rtl-v1'] = {'variant': 'calories-rtl-v1',
 'reference_sha256': '0be204f564ee6287d99a752f7d5f816df77c43f4ec322bc810781c1bbbaf2d35',
 'title': 'وش فيه سعرات أكثر إذا الوزن واحد؟',
 'subtitle': 'السعرات التقريبية في كل 100 غرام',
 'unit': 'kcal',
 'basis': {'quantity': 100, 'unit': 'g'},
 'note': '',
 'rows': [{'label': 'برجر لحم بالجبن', 'low': 310, 'high': 310},
          {'label': 'ساندوتش شاورما دجاج', 'low': 245, 'high': 245},
          {'label': 'ساندوتش فطور بيض وجبن', 'low': 230, 'high': 230},
          {'label': 'كبسة دجاج', 'low': 150, 'high': 150},
          {'label': 'مكرونة باللحم المفروم وصلصة الطماطم',
           'low': 120,
           'high': 120}],
 'scale': {'min': 0, 'max': 310, 'direction': 'rtl'},
 'layout': {'canvas': [1080, 1920],
            'bar_axis': [75, 897],
            'bar_y': [594, 814, 1034, 1254, 1474]},
 'number_format': {'digits': 'english', 'text_direction': 'rtl'}}
FILES['calories-rtl-v1'] = 'calories-rtl.png'

SPECS['protein-rtl-v1']={'variant': 'protein-rtl-v1', 'reference_sha256': 'ac65db3587d19adbeb60dcc782d4db0bfadc54b4c912e0710bf7abcbed4329b6', 'title': 'وش فيه بروتين أكثر؟', 'subtitle': 'البروتين التقريبي في كل 100 غرام', 'unit': 'g protein', 'basis': {'quantity': 100, 'unit': 'g'}, 'note': '', 'rows': [{'label': 'صدر دجاج مشوي بدون جلد', 'low': 32, 'high': 32}, {'label': 'تونة معلبة بالماء والملح', 'low': 25, 'high': 25}, {'label': 'فول سوداني محمص', 'low': 24, 'high': 24}, {'label': 'بيض مسلوق', 'low': 14, 'high': 14}, {'label': 'فول مدمس سادة', 'low': 8, 'high': 8}], 'scale': {'min': 0, 'max': 32, 'direction': 'rtl'}, 'layout': {'canvas': [1080, 1920], 'bar_axis': [74, 892], 'bar_y': [545, 766, 987, 1209, 1430]}, 'number_format': {'digits': 'english', 'text_direction': 'rtl'}}
FILES['protein-rtl-v1']='protein-rtl.png'

SPECS['fuel-rtl-v1'] = {'variant': 'fuel-rtl-v1',
 'reference_sha256': '9db7bba5027d57c5de07d0faf72113fcbaf2c1cd81e3d7c9fc482f03823aea3f',
 'title': 'مشوار 300 كم، كم يحتاج بنزين؟',
 'subtitle': 'صرف البنزين التقريبي لموديلات 2026',
 'unit': 'L',
 'basis': {'quantity': 300, 'unit': 'km'},
 'note': '',
 'rows': [{'label': 'كامري هايبرد LE', 'low': 10.8, 'high': 10.8},
          {'label': 'أكسنت L', 'low': 15.9, 'high': 15.9},
          {'label': 'لاندكروزر GXR1', 'low': 29.7, 'high': 29.7},
          {'label': 'نيسان باترول XE', 'low': 30.9, 'high': 30.9},
          {'label': 'جمس يوكون إليفيشن 5.3', 'low': 33.7, 'high': 33.7}],
 'scale': {'min': 0, 'max': 34, 'direction': 'rtl'},
 'layout': {'canvas': [1080, 1920], 'bar_axis': [74, 892], 'bar_y': [545, 766, 987, 1209, 1430]},
 'number_format': {'digits': 'english', 'text_direction': 'rtl'}}
FILES['fuel-rtl-v1'] = 'fuel-rtl.png'

def validate_reference_variant(image, spec, *, raw=None):
    if not isinstance(spec,dict):raise ValueError('Comparison variant spec must be an object')
    variant=spec.get('variant')
    if not isinstance(variant,str) or variant not in SPECS:
        raise ValueError('Unknown comparison variant')
    expected=SPECS[variant]
    # Canonical JSON distinguishes bool from int and rejects nonfinite values.
    try:
        supplied=json.dumps(spec,ensure_ascii=False,sort_keys=True,allow_nan=False)
        canonical=json.dumps(expected,ensure_ascii=False,sort_keys=True,allow_nan=False)
    except (ValueError,TypeError):
        raise ValueError('Invalid comparison variant data') from None
    if supplied!=canonical:
        raise ValueError('Comparison variant data/geometry differs from approved reference')
    if raw is not None and hashlib.sha256(raw).hexdigest()!=expected['reference_sha256']:
        raise ValueError('Comparison variant export bytes changed')
    path=ROOT/'assets/comparison/variants'/FILES[variant]
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected['reference_sha256']:
        raise ValueError('Comparison variant reference bytes changed')
    with Image.open(path) as reference:
        reference=reference.convert('RGB')
        if image.size!=(1080,1920) or ImageChops.difference(image.convert('RGB'),reference).getbbox():
            raise ValueError('Comparison variant pixels differ from approved reference')


def validate_manifest_binding(card, frame):
    """The approved manifest must carry the same explicit variant/spec."""
    if not isinstance(card,dict) or not isinstance(frame,dict):
        raise ValueError('Comparison review/manifest must be objects')
    c=card.get('comparison',{})
    f=frame.get('comparison',{})
    if (isinstance(c,dict) and 'variant' in c) or (isinstance(f,dict) and 'variant' in f):
        if (card.get('template')!='comparison' or frame.get('template')!='comparison'
                or c!=f):
            raise ValueError('Comparison variant differs from approved manifest')
