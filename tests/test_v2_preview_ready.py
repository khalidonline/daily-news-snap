"""Incomplete overlay evidence must fail before a preview seal is written."""
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
