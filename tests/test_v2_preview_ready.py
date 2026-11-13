"""Incomplete overlay evidence must fail before a preview seal is written."""
import hashlib
import json
from pathlib import Path
import shutil
import socket

import pytest
from publishing_v2 import prepared_information as prep

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def draft(tmp_path,monkeypatch):
    source=ROOT/'approved/radio-school-20261031'
    p=tmp_path/'approved/radio-school-20261031'
    shutil.copytree(source,p)
    (tmp_path/'publishing_v2').mkdir()
    shutil.copyfile(ROOT/'publishing_v2/design-settings.json',tmp_path/'publishing_v2/design-settings.json')
    # This archived radio-card fixture predates the Nov 11 editorial-only master
    # update. Rebind the TEMPORARY synthetic draft only, for the two reviewed
    # byte identities; a future unknown master must still fail this fixture.
    settings=(tmp_path/'publishing_v2/design-settings.json').read_bytes()
    report_path=p/'design-review.json'
    report=json.loads(report_path.read_text())
    assert report['settings_sha256']=='61a6ea74222fe325f213526db5ace3a734b85dc0456c1fa072f85c82e0f16504'
    assert hashlib.sha256(settings).hexdigest()=='637f0112adda4b391cbe2a3bbf5668afd9f970a8692147f09eac858a9198ec74'
    report['settings_sha256']=hashlib.sha256(settings).hexdigest()
    report_path.write_text(json.dumps(report))
    for name in ('manifest.json','archive-approval.json'):
        d=json.loads((p/name).read_text());d['approved']=False
        (p/name).write_text(json.dumps(d))
    (p/'prepared.json').unlink()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket,'socket',lambda *a,**k:pytest.fail('preview must stay offline'))
    return p

def test_incomplete_overlay_cannot_seal_preview(draft):
    r=json.loads((draft/'design-review.json').read_text())
    r['review']['overlay_checked']=False
    (draft/'design-review.json').write_text(json.dumps(r))
    with pytest.raises(ValueError,match='mobile/editorial'):
        prep.prepare_local_preview(draft)
    assert not (draft/'prepared.json').exists()

def test_missing_archive_baseline_cannot_seal_preview(draft):
    a=json.loads((draft/'archive-approval.json').read_text())
    a.pop('empty_profile_confirmation',None)
    (draft/'archive-approval.json').write_text(json.dumps(a))
    with pytest.raises(ValueError,match='archive'):
        prep.prepare_local_preview(draft)
    assert not (draft/'prepared.json').exists()

def test_complete_draft_seals_without_granting_approval(draft):
    before=(draft/'manifest.json').read_bytes()
    result=prep.prepare_local_preview(draft)
    assert result['status']=='PREPARED_NOT_AUTHORIZED'
    assert (draft/'manifest.json').read_bytes()==before
    assert json.loads((draft/'archive-approval.json').read_text())['approved'] is False
    assert prep.verify_prepared(draft)==result
