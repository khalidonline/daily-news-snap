"""Offline bridge tests: real fit/render, no provider or owner approval."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket

import pytest
from PIL import Image

from publishing_v2.editorial_production import approve_text, TEXT_CHECKS


def module():
    assert importlib.util.find_spec('publishing_v2.autopilot.information_bridge'), 'bridge missing'
    from publishing_v2.autopilot import information_bridge
    return information_bridge


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    (tmp_path/'publishing_v2').mkdir()
    (tmp_path/'publishing_v2/design-settings.json').write_bytes((root/'publishing_v2/design-settings.json').read_bytes())
    source = tmp_path/'cached'; source.mkdir()
    Image.new('RGB', (1200, 800), 'blue').save(source/'source-00.jpg')
    raw = (source/'source-00.jpg').read_bytes()
    package = {'title':'اختبار محلي', 'as_of':'2026-11-04T00:00:00+00:00', 'expires_at':'2099-01-01T00:00:00+00:00',
               'cards':[{'kind':'info','title':'خبر اليوم','body':'هذا نص تجريبي قصير.',
                         'punch':'هنا الخلاصة','image_caption':'صورة تجريبية',
                         'image':{'license':'CC0','asset_id':'test', 'sha256':hashlib.sha256(raw).hexdigest()}}],
               'sources':[{'url':'https://example.test/fixture','text':'synthetic test only'}]}
    class Agent:
        def run(self,*a,**kw):
            return {'checks':dict.fromkeys(TEXT_CHECKS, True),'repair_indices':[], 'reason':'Synthetic offline fixture'}
    approve_text(package, Agent())
    monkeypatch.setattr(socket, 'socket', lambda *a,**kw: pytest.fail('network forbidden'))
    return package, source, tmp_path


def stage(candidate):
    package, source, _ = candidate
    return module().stage(package, source, 'tawari-offline')


def test_real_fixed_template_stages_draft_without_authority(candidate):
    original=copy.deepcopy(candidate[0])
    result=stage(candidate)
    p=candidate[2]/'approved/tawari-offline'
    assert result['status']=='DRAFT_REQUIRES_REVIEW'
    assert result['preview_allowed'] is False
    assert candidate[0]==original
    manifest=json.loads((p/'manifest.json').read_text())
    archive=json.loads((p/'archive-approval.json').read_text())
    assert manifest['approved'] is False and archive['approved'] is False
    assert manifest['approved_destinations']==['STORY','SAVED_STORY']
    assert manifest['story_duration']=='ONE_WEEK'
    assert Image.open(p/'card-00.png').size==(1080,1920)
    fit=json.loads((p/'text-fit.json').read_text())[0]
    assert fit['fit'] is True
    assert fit['fields'][1]['text']==original['cards'][0]['body']
    report=json.loads((p/'design-review.json').read_text())
    assert report['review']=={} and report['status']=='PENDING_ACTUAL_REVIEW'
    assert not (p/'prepared.json').exists()
    assert not (p/'preview-receipt.json').exists()
    assert not (candidate[2]/'.github/information-publish-request.json').exists()
    from publishing_v2.prepared_information import prepare_local_preview
    with pytest.raises(ValueError): prepare_local_preview(p)


def test_same_name_never_overwrites_reviewed_or_delivered_bytes(candidate):
    stage(candidate)
    p=candidate[2]/'approved/tawari-offline/card-00.png'
    before=p.read_bytes()
    with pytest.raises(FileExistsError): stage(candidate)
    assert p.read_bytes()==before


@pytest.mark.parametrize('fault', ['overflow','three_cards','changed_source','missing_source','credit','video','stale_text','unsafe_name'])
def test_blocked_input_leaves_no_package(candidate, fault):
    package, source, root=candidate
    name='tawari-offline'
    if fault=='overflow':
        package['cards'][0]['body']='نص طويل '*150
        # Explicit synthetic review is not a fit override.
        from test_v2_autopilot_runtime import approve_fixture
        approve_fixture(package)
    elif fault=='three_cards': package['cards']*=3
    elif fault=='changed_source': (source/'source-00.jpg').write_bytes(b'changed')
    elif fault=='missing_source': (source/'source-00.jpg').unlink()
    elif fault=='credit': package['cards'][0]['image']['license']='CC BY 4.0'
    elif fault=='video': package['delivery']={'kind':'video'}
    elif fault=='stale_text': package['cards'][0]['title']='تعديل غير معتمد'
    elif fault=='unsafe_name': name='../escape'
    with pytest.raises((ValueError,OSError)):
        module().stage(package,source,name)
    assert not (root/'approved/tawari-offline').exists()


def test_handoff_has_complete_authorization_window(candidate):
    candidate[0]['as_of']='2026-11-04T00:00:00+00:00'
    from test_v2_autopilot_runtime import approve_fixture
    approve_fixture(candidate[0])
    stage(candidate)
    m=json.loads((candidate[2]/'approved/tawari-offline/manifest.json').read_text())
    assert m['not_before']==candidate[0]['as_of']


def test_offline_review_preview_authorization_and_dual_delivery(candidate, monkeypatch):
    """Synthetic approvals in temp Git only, not actual review or send evidence."""
    # This temporary repository is not the live approval authority. Match the
    # existing offline contract fixtures; production CI revocation checks stay on.
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    import subprocess
    from datetime import datetime, timezone
    from publishing_v2 import prepared_information as prep, information_request as req
    from publishing_v2 import deliver_information as delivery
    from publishing_v2.autopilot import fixed_information
    package=candidate[0]
    package['information_schema_version']=1
    package['research']={'claims':[{'id':'c1'}]}
    card=package['cards'][0]
    card['bullets']=[card.pop('body')]
    card.update(claim_ids=['c1'],image_query='synthetic photo')
    class Review:
        def run(self,*a,**kw):
            return {'checks':dict.fromkeys(TEXT_CHECKS,True),'repair_indices':[],
                    'reason':'Synthetic fixed text review only'}
    fixed_information.approve_text(package,Review())
    stage(candidate)
    root=candidate[2]; p=root/'approved/tawari-offline'
    read=lambda n:json.loads((p/n).read_text())
    def write(n,d): (p/n).write_text(json.dumps(d))
    report=read('design-review.json')
    report['review']={'reference':'OFFLINE SYNTHETIC REVIEW, NOT OWNER AUTHORITY','mobile_width':390,
                     **dict.fromkeys(('saudi_editorial','approved_wording','photos_and_captions',
                                      'cta_visible','overlay_checked','approved_typography'),True),
                     'overlay_destinations':{'STORY':'synthetic test','SAVED_STORY':'synthetic test'}}
    report['cards'][0]['palette_samples']={'background':[10,10,30,30], 'green':[935,142,1005,144],
                                         'cta_background':[70,1680,80,1710]}
    write('design-review.json',report)
    archive=read('archive-approval.json');archive['empty_profile_confirmation']='OFFLINE TEST ONLY'
    write('archive-approval.json',archive)
    prep.prepare_local_preview(p)  # Actual renderer pixels and both destination validators.
    with pytest.raises((ValueError,OSError)): req.authorize_request(p,'synthetic authority',datetime.now(timezone.utc),root/'early')
    subprocess.run(['git','init','-q',str(root)],check=True)
    subprocess.run(['git','add','.'],check=True)
    subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.test','commit','-qm','offline draft'],check=True)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    prep.compare_uploaded_preview(p,root,head)  # Local immutable Git fixture, never network/main upload.
    staged=req.authorize_request(p,'OFFLINE SYNTHETIC OWNER AUTHORIZATION',datetime.now(timezone.utc),root/'staged')
    before=(p/'card-00.png').read_bytes()
    for filename in ('manifest.json','archive-approval.json'):
        (p/filename).write_bytes((staged/'approved/tawari-offline'/filename).read_bytes())
    calls=[]
    def fake_run(args,check):
        calls.append(args)
        if args[2]=='publishing_v2.bundle_api':
            from publishing_v2.bundle_api import load_package
            from publishing_v2.design_contract import validate_design
            _,_,media=load_package(args[-1])
            media.check_approval()
            validate_design(media,read('design-review.json'),'STORY')
    monkeypatch.setattr(delivery.subprocess,'run',fake_run)
    result=delivery.deliver(p)
    assert [c[2] for c in calls]==['publishing_v2.bundle_api','publishing_v2.bundle_api','publishing_v2.saved_story_api']
    assert result['identity']==read('archive-approval.json')['identity']
    assert result['STORY']==result['SAVED_STORY']=='CONFIRMED_BY_PUBLISHER'
    assert (p/'card-00.png').read_bytes()==before


def test_two_cards_and_review_only_credits_preserve_public_order(candidate):
    package,source,root=candidate
    second=copy.deepcopy(package['cards'][0]);second['kind']='story';second['title']='الخبر الثاني'
    Image.new('RGB',(1200,800),'red').save(source/'source-01.jpg')
    second['image']['sha256']=hashlib.sha256((source/'source-01.jpg').read_bytes()).hexdigest()
    second['image']['asset_id']='second'
    package['cards'].extend([second,{'kind':'credits','body':'internal references'}])
    from test_v2_autopilot_runtime import approve_fixture
    approve_fixture(package)
    result=stage(candidate)
    p=root/result['package']
    manifest=json.loads((p/'manifest.json').read_text())
    assert len(manifest['media'])==2
    assert json.loads((p/'archive-approval.json').read_text())['public_indices']==[1,2]
    assert not (p/'card-02.png').exists()
    assert json.loads((p/'autopilot-input.json').read_text())['cards'][-1]['kind']=='credits'


def test_absolute_name_is_rejected_before_any_output(candidate):
    package,source,root=candidate
    with pytest.raises(ValueError,match='name'):
        module().stage(package,source,str(root/'approved/absolute-name'))
    assert not (root/'approved').exists()


def test_staged_pixels_are_exact_shared_template_output(candidate):
    import io
    from publishing_v2.fixed_information_template import render
    package,source,root=candidate
    stage(candidate)
    card=package['cards'][0]
    with Image.open(source/'source-00.jpg') as photo:
        expected,_=render(card['title'],[card['body']],card['punch'],[photo.convert('RGB')],[card['image_caption']])
    with Image.open(root/'approved/tawari-offline/card-00.png') as actual:
        assert actual.size==expected.size==(1080,1920)
        assert actual.tobytes()==expected.tobytes()
