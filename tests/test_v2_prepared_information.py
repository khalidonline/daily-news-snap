import hashlib
import importlib
import json
from pathlib import Path

import pytest
import publishing_v2


def module():
    assert importlib.util.find_spec('publishing_v2.prepared_information'), 'preparation module missing'
    return importlib.import_module('publishing_v2.prepared_information')


@pytest.fixture
def package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p=tmp_path/'approved/example'
    p.mkdir(parents=True)
    (tmp_path/'publishing_v2').mkdir()
    (tmp_path/'publishing_v2/design-settings.json').write_text('{}')
    (p/'card.png').write_bytes(b'final')
    (p/'source.jpg').write_bytes(b'source')
    (p/'design-review.json').write_text('{}')
    digest=lambda b:hashlib.sha256(b).hexdigest()
    data={'approved':False,'account':'executivesaudi','content_type':'information',
          'approved_destinations':['STORY','SAVED_STORY'],'story_duration':'ONE_WEEK',
          'title':'example','expires_at':'2099-01-01T00:00:00Z',
          'media':[{'path':'approved/example/card.png','sha256':digest(b'final'),
                    'source_assets':[{'path':'approved/example/source.jpg','sha256':digest(b'source')}]}]}
    (p/'manifest.json').write_text(json.dumps(data))
    (p/'archive-approval.json').write_text(json.dumps({'approved':False,'title':'example'}))
    return p


def test_prepare_does_not_authorize_or_network(package, monkeypatch):
    import socket
    monkeypatch.setattr(socket,'socket',lambda *a,**k:pytest.fail('network during preparation'))
    before=(package/'manifest.json').read_bytes()
    result=module().prepare(package)
    assert result['status']=='PREPARED_NOT_AUTHORIZED'
    assert (package/'manifest.json').read_bytes()==before
    assert module().verify_prepared(package)==result


@pytest.mark.parametrize('name',['card.png','source.jpg','design-review.json','manifest.json',
                                 'archive-approval.json','../../publishing_v2/design-settings.json'])
def test_changed_content_invalidates_seal(package,name):
    m=module();m.prepare(package)
    path=package/name
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises((ValueError,OSError)):m.verify_prepared(package)


def test_only_explicit_authorization_metadata_can_change(package):
    m=module();m.prepare(package)
    data=json.loads((package/'manifest.json').read_text());data['approved']=True
    data['owner_review']={'reference':'owner approved','reviewed_at':'2026-10-31T00:00:00Z'}
    (package/'manifest.json').write_text(json.dumps(data))
    a=json.loads((package/'archive-approval.json').read_text());a.update(approved=True,owner_authorization='publish',manifest_sha256='new')
    (package/'archive-approval.json').write_text(json.dumps(a))
    assert m.verify_prepared(package)['status']=='PREPARED_NOT_AUTHORIZED'


@pytest.mark.parametrize('change',[{'content_type':'challenge'}, {'approved_destinations':['STORY','SPOTLIGHT']}, {'story_duration':'ONE_DAY'}])
def test_other_routes_rejected(package,change):
    d=json.loads((package/'manifest.json').read_text());d.update(change)
    (package/'manifest.json').write_text(json.dumps(d))
    with pytest.raises(ValueError):module().prepare(package)


@pytest.mark.parametrize('unsafe',['../escape.png','/tmp/escape.png'])
def test_unsafe_asset_paths_rejected(package,unsafe):
    d=json.loads((package/'manifest.json').read_text());d['media'][0]['path']=unsafe
    (package/'manifest.json').write_text(json.dumps(d))
    with pytest.raises(ValueError):module().prepare(package)


def test_symlink_escape_rejected(package,tmp_path):
    outside=tmp_path.parent/'escape-card';outside.write_bytes(b'final')
    (package/'card.png').unlink();(package/'card.png').symlink_to(outside)
    with pytest.raises(ValueError):module().prepare(package)
