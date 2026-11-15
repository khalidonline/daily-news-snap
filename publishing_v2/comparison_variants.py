"""Closed, immutable reference variants, not a general chart renderer.

Only the two specifically reviewed exports and their complete semantic specs
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
