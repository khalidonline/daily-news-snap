"""Approval request contract: real files/git, no provider or network."""
import importlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import pytest
from test_v2_preview_ready import draft as base_draft
from test_v2_uploaded_preview import remote
from publishing_v2 import prepared_information as prep

NOW=datetime(2026,10,31,12,tzinfo=timezone.utc)
REFERENCE='Khalid explicitly approves this exact preview: انشر'

@pytest.fixture
def draft(base_draft):
    # Synthetic validity window: tests must not expire with the real old post.
    for name in ('manifest.json','archive-approval.json'):
        p=base_draft/name;d=json.loads(p.read_text());d['expires_at']='2099-01-01T00:00:00+00:00'
        if name=='manifest.json':d['not_before']='2000-01-01T00:00:00+00:00'
        p.write_text(json.dumps(d))
    return base_draft

def module():
    assert importlib.util.find_spec('publishing_v2.information_request'), 'request module missing'
    return importlib.import_module('publishing_v2.information_request')

def read(p): return json.loads(p.read_text())

@pytest.fixture
def preview(draft,remote):
    prep.compare_uploaded_preview(draft,*remote)
    return draft

def test_verified_preview_records_exact_draft_hashes(draft,remote):
    prep.compare_uploaded_preview(draft,*remote)
    path=draft/'preview-receipt.json'
    assert path.exists(), 'durable preview receipt missing'
    r=read(path)
    assert r['commit']==remote[1]
    assert r['files'][str(draft.relative_to(remote[0])/'card.png')]==prep.digest((draft/'card.png').read_bytes())

@pytest.mark.parametrize('fault',['no_sources'])
def test_incomplete_provenance_blocks_before_preview_seal(draft,fault):
    d=read(draft/'manifest.json')
    if fault=='no_sources':d['media'][0]['source_assets']=[];d['owner_review']['approved_source_sha256']=[]
    else:d['media'][0]['source_assets'][0].pop(fault)
    (draft/'manifest.json').write_text(json.dumps(d))
    with pytest.raises(ValueError,match='[Ss]ource|editorial|provenance'):
        prep.prepare_local_preview(draft)
    assert not (draft/'prepared.json').exists()
    assert not (draft/'preview-receipt.json').exists()

def test_archival_reference_fields_do_not_block_preparation(draft):
    d=read(draft/'manifest.json')
    for source in d['media'][0]['source_assets']:
        for key in ('rights_status','owner_reference','source_url','description'):
            source.pop(key,None)
    (draft/'manifest.json').write_text(json.dumps(d))
    result=prep.prepare_local_preview(draft)
    assert result['status']=='PREPARED_NOT_AUTHORIZED'

def test_authorization_stages_transaction_without_mutating_draft(preview,tmp_path):
    m=module(); before={p:p.read_bytes() for p in preview.iterdir() if p.is_file()}
    staged=m.authorize_request(preview,REFERENCE,NOW,tmp_path/'staged')
    assert {p:p.read_bytes() for p in before}==before
    req=read(staged/m.REQUEST_PATH)
    assert req['package']=='radio-school-20261031'
    assert req['destinations']==['STORY','SAVED_STORY']
    assert read(staged/'approved/radio-school-20261031/manifest.json')['approved'] is True
    assert sorted(str(p.relative_to(staged)) for p in staged.rglob('*') if p.is_file())==[
        '.github/information-publish-request.json',
        'approved/radio-school-20261031/archive-approval.json',
        'approved/radio-school-20261031/manifest.json']

@pytest.mark.parametrize('fault',['receipt','media','source','settings','reference','expired','symlink','rights','already_approved'])
def test_invalid_input_writes_nothing(preview,tmp_path,fault):
    m=module(); ref=REFERENCE; now=NOW
    if fault=='receipt': (preview/'preview-receipt.json').unlink()
    elif fault in ('media','source','settings'):
        path={'media':preview/'card.png','source':preview/'newspaper.jpg','settings':tmp_path/'publishing_v2/design-settings.json'}[fault]
        path.write_bytes(path.read_bytes()+b'changed')
    elif fault=='reference':ref=''
    elif fault=='expired':now=datetime(2099,1,1,tzinfo=timezone.utc)
    elif fault=='symlink':
        original=(preview/'card.png').read_bytes();(preview/'card.png').unlink()
        (tmp_path/'outside.png').write_bytes(original);(preview/'card.png').symlink_to(tmp_path/'outside.png')
    else:
        d=read(preview/'manifest.json')
        if fault=='rights':d['media'][0]['source_assets'][0]['rights_status']='permission_unknown'
        else:d['approved']=True
        (preview/'manifest.json').write_text(json.dumps(d))
    before={p:p.read_bytes() for p in preview.iterdir() if p.is_file()}
    with pytest.raises((ValueError,OSError,RuntimeError)):
        m.authorize_request(preview,ref,now,tmp_path/'staged')
    assert not (tmp_path/'staged').exists()
    assert {p:p.read_bytes() for p in before}==before

def commit(root):
    subprocess.run(['git','add','.'],cwd=root,check=True)
    subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.test','commit','-qm','approval'],cwd=root,check=True)
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()

@pytest.fixture
def authorized(preview,tmp_path):
    import shutil
    m=module(); staged=m.authorize_request(preview,REFERENCE,NOW,tmp_path.parent/(tmp_path.name+'-staged'))
    for path in staged.rglob('*'):
        if path.is_file():
            dest=tmp_path/path.relative_to(staged);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    commit(tmp_path)
    return tmp_path,read(tmp_path/m.REQUEST_PATH)

def test_valid_request_selects_only_exact_package(authorized):
    root,r=authorized
    assert module().validate_request(root,r,NOW)==root/'approved/radio-school-20261031'

@pytest.mark.parametrize('fault',['package','hash','expiry','identity','destination','owner','draft'])
def test_request_substitution_rejected(authorized,fault):
    root,r=authorized
    if fault=='draft':
        p=root/'approved/radio-school-20261031/manifest.json';d=read(p);d['approved']=False;p.write_text(json.dumps(d))
    else:
        key,value={'package':('package','../elsewhere'),'hash':('manifest_sha256','0'*64),'expiry':('expires_at','2000-01-01T00:00:00Z'),'identity':('identity','0'*64),'destination':('destinations',['SPOTLIGHT']),'owner':('owner_reference','')}[fault]
        r[key]=value
    with pytest.raises((ValueError,RuntimeError)):
        module().validate_request(root,r,NOW)
