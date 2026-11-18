"""Exact approved inputs; no test grants publication authorization."""
import copy
import hashlib
import io
import json
from pathlib import Path
import pytest
from PIL import Image
from publishing_v2.comparison_template import validate, EXAMPLE, REFERENCE

ROOT=Path(__file__).resolve().parents[1]
SPECS={
'pictogram-count-v1': dict(variant='pictogram-count-v1',reference_sha256='6c10247642fe38b6fc615a9fa88be579fcd19ce3727a578c510d09fe8150a021',title='كم ملعقة سكر في مشروبك؟',subtitle='في كل 250 مل من المشروب',unit='ملاعق صغيرة تقريبا',basis={'quantity':250,'unit':'ml'},note='',rows=[{'label':'ريد بول','count':7},{'label':'كوكاكولا','count':7},{'label':'برتقال معصور طازج','count':5},{'label':'كراميل ماكياتو من ستاربكس','count':4}],pictogram={'kind':'teaspoon','capacity':7,'direction':'rtl'},layout={'canvas':[1080,1920],'row_step':286,'pictogram_y':[620,906,1192,1478]}),
'annotated-range-v1':dict(variant='annotated-range-v1',reference_sha256='ae3f0e81f86231260e4052f33fc8abc3dfd05a04235da698de21003306080d1d',title='ساعة على جوالك كم تسحب من باقتك؟',subtitle='ساعة كاملة لكل تطبيق',unit='بالميقا تقريبا',basis={'quantity':1,'unit':'hour'},note='استهلاك الفيديو يتغير حسب الجودة والمقاطع.',rows=[{'label':'تيك توك','low':500,'high':1000,'usage':'تصفح المقاطع'},{'label':'سناب','low':360,'high':1200,'usage':'مقاطع الأضواء والستوري'},{'label':'يوتيوب','low':240,'high':500,'usage':'الجودة التلقائية إذا اختارت 480p'},{'label':'إكس','low':50,'high':60,'usage':'قراءة تغريدات بدون فيديو'},{'label':'خرائط قوقل','low':30,'high':50,'usage':'تتبع الطريق'}],scale={'min':0,'max':1200,'direction':'rtl'},layout={'canvas':[1080,1920],'bar_axis':[80,1005],'bar_y':[604,807,1010,1213,1416]})}
FILES={'pictogram-count-v1':'sugar-pictogram.png','annotated-range-v1':'mobile-data-ranges.png'}
SPECS['calories-rtl-v1']={'variant': 'calories-rtl-v1', 'reference_sha256': '0be204f564ee6287d99a752f7d5f816df77c43f4ec322bc810781c1bbbaf2d35', 'title': 'وش فيه سعرات أكثر إذا الوزن واحد؟', 'subtitle': 'السعرات التقريبية في كل 100 غرام', 'unit': 'kcal', 'basis': {'quantity': 100, 'unit': 'g'}, 'note': '', 'rows': [{'label': 'برجر لحم بالجبن', 'low': 310, 'high': 310}, {'label': 'ساندوتش شاورما دجاج', 'low': 245, 'high': 245}, {'label': 'ساندوتش فطور بيض وجبن', 'low': 230, 'high': 230}, {'label': 'كبسة دجاج', 'low': 150, 'high': 150}, {'label': 'مكرونة باللحم المفروم وصلصة الطماطم', 'low': 120, 'high': 120}], 'scale': {'min': 0, 'max': 310, 'direction': 'rtl'}, 'layout': {'canvas': [1080, 1920], 'bar_axis': [75, 897], 'bar_y': [594, 814, 1034, 1254, 1474]}, 'number_format': {'digits': 'english', 'text_direction': 'rtl'}}
FILES['calories-rtl-v1']='calories-rtl.png'

SPECS['protein-rtl-v1']={'variant': 'protein-rtl-v1', 'reference_sha256': 'ac65db3587d19adbeb60dcc782d4db0bfadc54b4c912e0710bf7abcbed4329b6', 'title': 'وش فيه بروتين أكثر؟', 'subtitle': 'البروتين التقريبي في كل 100 غرام', 'unit': 'g protein', 'basis': {'quantity': 100, 'unit': 'g'}, 'note': '', 'rows': [{'label': 'صدر دجاج مشوي بدون جلد', 'low': 32, 'high': 32}, {'label': 'تونة معلبة بالماء والملح', 'low': 25, 'high': 25}, {'label': 'فول سوداني محمص', 'low': 24, 'high': 24}, {'label': 'بيض مسلوق', 'low': 14, 'high': 14}, {'label': 'فول مدمس سادة', 'low': 8, 'high': 8}], 'scale': {'min': 0, 'max': 32, 'direction': 'rtl'}, 'layout': {'canvas': [1080, 1920], 'bar_axis': [74, 892], 'bar_y': [545, 766, 987, 1209, 1430]}, 'number_format': {'digits': 'english', 'text_direction': 'rtl'}}
FILES['protein-rtl-v1']='protein-rtl.png'

def case(variant):
 raw=(ROOT/'assets/comparison/variants'/FILES[variant]).read_bytes()
 return raw,Image.open(io.BytesIO(raw)).convert('RGB'),copy.deepcopy(SPECS[variant])

@pytest.mark.parametrize('variant',SPECS)
def test_approved_variant_exact_png(variant):
 raw,image,spec=case(variant)
 # Before implementation these two real approved exports fail the old renderer.
 validate(image,spec)
 assert hashlib.sha256(raw).hexdigest()==spec['reference_sha256']

@pytest.mark.parametrize('variant',SPECS)
@pytest.mark.parametrize('change',['data','label','unit','basis','note','geometry','subtype','extra'])
def test_rejects_changed_spec(variant,change):
 raw,image,spec=case(variant)
 if change=='data':spec['rows'][0]['count' if variant=='pictogram-count-v1' else 'low']=99
 if change=='label':spec['rows'][0]['label']='wrong'
 if change=='unit':spec['unit']='wrong'
 if change=='basis':spec['basis']['quantity']=99
 if change=='note':spec['note']='wrong'
 if change=='geometry':spec['layout']['canvas']=[1920,1080]
 if change=='subtype':spec['variant']='unknown'
 if change=='extra':spec['ignore_validation']=True
 with pytest.raises(ValueError):validate(image,spec)

@pytest.mark.parametrize('variant',SPECS)
@pytest.mark.parametrize('position',[(100,100),(500,260),(700,630),(150,1700)])
def test_rejects_changed_pixels(variant,position):
 raw,image,spec=case(variant);image.putpixel(position,(255,0,0))
 with pytest.raises(ValueError):validate(image,spec)

def test_caffeine_reference_remains_valid():
 validate(Image.open(REFERENCE).convert('RGB'),EXAMPLE)

@pytest.mark.parametrize('variant',SPECS)
@pytest.mark.parametrize('placement',['STORY','SAVED_STORY'])
def test_shared_design_gate_preserves_approved_variant(variant,placement):
 from test_v2_design_contract import fixture_card
 from publishing_v2.design_contract import validate_design
 raw,image,spec=case(variant);_,report=fixture_card()
 report['destinations']=['STORY','SAVED_STORY']
 report['review']['overlay_destinations']={p:'Offline fixture only; not a production review' for p in report['destinations']}
 report['cards']=[dict(template='comparison',comparison=spec,sha256=hashlib.sha256(raw).hexdigest(),palette_samples={'background':[10,10,30,30],'green':[935,142,1005,144],'cta_background':[70,1680,80,1710]})]
 assert validate_design([(Path('card.png'),raw)],report,placement)['status']=='validated'
 for mutation in ['hash','review','destination','classification']:
  bad=copy.deepcopy(report)
  if mutation=='hash':bad['cards'][0]['sha256']='0'*64
  if mutation=='review':bad['review']['approved_wording']=False
  if mutation=='destination':bad['review']['overlay_destinations'].pop(placement)
  if mutation=='classification':bad['content_type']='challenge'
  from publishing_v2.bundle_api import BundleError
  with pytest.raises(BundleError):validate_design([(Path('card.png'),raw)],bad,placement)

@pytest.mark.parametrize('variant',SPECS)
def test_variant_is_bound_to_manifest(variant):
 from publishing_v2.comparison_variants import validate_manifest_binding
 card={'template':'comparison','comparison':copy.deepcopy(SPECS[variant])}
 frame=copy.deepcopy(card);validate_manifest_binding(card,frame)
 for mutation in ['omit','variant','data','template']:
  bad=copy.deepcopy(frame)
  if mutation=='omit':bad.pop('comparison')
  if mutation=='variant':bad['comparison']['variant']='unknown'
  if mutation=='data':bad['comparison']['unit']='wrong'
  if mutation=='template':bad['template']='information'
  with pytest.raises(ValueError):validate_manifest_binding(card,bad)
  with pytest.raises(ValueError):validate_manifest_binding(bad,card)

@pytest.mark.parametrize('variant',SPECS)
def test_reference_tamper_is_rejected(variant,tmp_path,monkeypatch):
 import publishing_v2.comparison_variants as variants
 raw,image,spec=case(variant)
 dest=tmp_path/'assets/comparison/variants';dest.mkdir(parents=True)
 (dest/FILES[variant]).write_bytes(raw+b'tamper')
 monkeypatch.setattr(variants,'ROOT',tmp_path)
 with pytest.raises(ValueError,match='reference bytes changed'):validate(image,spec)

@pytest.mark.parametrize('variant',SPECS)
def test_rows_annotations_and_unknown_geometry_cannot_be_omitted(variant):
 raw,image,spec=case(variant)
 for key in ['rows','layout','reference_sha256','basis']:
  bad=copy.deepcopy(spec);bad.pop(key)
  with pytest.raises(ValueError):validate(image,bad)
 bad=copy.deepcopy(spec);bad['rows'].pop()
 with pytest.raises(ValueError):validate(image,bad)
 if variant=='annotated-range-v1':
  bad=copy.deepcopy(spec);bad['rows'][0].pop('usage')
  with pytest.raises(ValueError):validate(image,bad)

@pytest.mark.parametrize('variant',SPECS)
def test_shared_gate_rejects_reencoded_reference_bytes(variant):
 from test_v2_design_contract import fixture_card
 from publishing_v2.design_contract import validate_design
 raw,image,spec=case(variant);_,report=fixture_card()
 reencoded=io.BytesIO();image.save(reencoded,format='PNG',compress_level=0)
 other=reencoded.getvalue();assert other!=raw
 report['cards']=[dict(template='comparison',comparison=spec,sha256=hashlib.sha256(other).hexdigest(),palette_samples={'background':[10,10,30,30],'green':[935,142,1005,144],'cta_background':[70,1680,80,1710]})]
 with pytest.raises(ValueError,match='export bytes'):validate_design([(Path('card.png'),other)],report,'STORY')
