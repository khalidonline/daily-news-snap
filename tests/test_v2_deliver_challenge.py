"""Offline tests for the shared reviewed-challenge route, never live clients."""
import copy
import hashlib
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import pytest
from publishing_v2.bundle_api import BundleError, ApprovedMedia

DIGEST=hashlib.sha256(b'exact-video').hexdigest()
DUE='2026-11-17T10:00:00+00:00'

def module():
    return importlib.import_module('publishing_v2.deliver_challenge')

def data():
    return {'format':'reviewed-challenge-video-v1','content_type':'challenge','approved':True,
            'approved_destinations':['STORY','SPOTLIGHT'],'not_before':DUE,
            'expires_at':'2099-01-01T00:00:00+00:00'}

@pytest.mark.parametrize('digest', ['', 'x'*64, '0'*64])
def test_exact_expected_hash_required(digest):
    m=module()
    with pytest.raises(BundleError):m.check_binding(data(),[(Path('final.mp4'),b'exact-video')],digest)

@pytest.mark.parametrize('destinations',[['STORY'],['SPOTLIGHT'],['STORY','SAVED_STORY'],['STORY','SPOTLIGHT','STORY']])
def test_only_explicit_two_destinations(destinations):
    m=module();d=data();d['approved_destinations']=destinations
    with pytest.raises(BundleError):m.check_binding(d,[(Path('final.mp4'),b'exact-video')],DIGEST)

@pytest.mark.parametrize('not_before',[None,'2026-11-17T10:00:00','nonsense','2100-01-01T00:00:00Z'])
def test_scheduled_bound_must_be_aware_and_before_expiry(not_before):
    m=module();d=data();d['not_before']=not_before
    with pytest.raises(BundleError):m.check_binding(d,[(Path('final.mp4'),b'exact-video')],DIGEST)

def test_before_due_blocks_all_provider_and_journal_work():
    m=module()
    with patch.object(m,'validate_package',return_value=('identity','title',[],data())), patch.object(m,'BundleClient',side_effect=AssertionError('provider initialized')), patch.object(m,'GitHubJournal',side_effect=AssertionError('journal initialized')):
        with pytest.raises(BundleError,match='before'):
            m.run('sample-package',DIGEST,action='publish',now=datetime(2026,11,17,9,59,59,tzinfo=timezone.utc))

def test_validate_returns_without_clients_or_journals():
    m=module()
    with patch('publishing_v2.challenge_visual_review.validate_challenge_images'), patch.object(m,'validate_package',return_value=('identity','title',[],data())), patch.object(m,'BundleClient',side_effect=AssertionError('provider initialized')), patch.object(m,'GitHubJournal',side_effect=AssertionError('journal initialized')):
        result=m.run('sample-package',DIGEST)
    assert result['status']=='VALIDATED_NOT_PUBLISHED' and result['sha256']==DIGEST

class Journal:
    def __init__(self,state=None):self.state=copy.deepcopy(state or {})
    def read(self):return copy.deepcopy(self.state)
    def save(self,state):self.state=copy.deepcopy(state)

class Client:
    team='team'
    def __init__(self):self.sent=[];self.uploads=[]
    def check(self):pass
    def ensure_capacity(self,count):pass
    def upload(self,item):self.uploads.append(item);return 'upload-'+str(len(self.uploads))
    def create(self,title,upload):self.sent.append('STORY');return 'story-post'
    def create_spotlight(self,title,upload):self.sent.append('SPOTLIGHT');return 'spot-post'
    def wait(self,post_id):pass
    def call(self,path):
        dest='STORY' if path.endswith('story-post') else 'SPOTLIGHT'
        return {'id':path.rsplit('/',1)[1],'teamId':'team','status':'POSTED','externalData':{'SNAPCHAT':{'status':'PUBLISHED','type':dest,'sourceUploadIds':['upload-1' if dest=='STORY' else 'upload-2']}}}

def test_uncertain_other_destination_blocks_any_new_upload():
    m=module();client=Client();journals={'STORY':Journal(),'SPOTLIGHT':Journal({'1':{'status':'SENDING','upload_id':'uncertain'}})}
    with pytest.raises(BundleError,match='Uncertain'):
        m.deliver(client,journals,'title',[],DIGEST)
    assert client.sent==[] and client.uploads==[]

def test_two_destinations_publish_once_and_reconcile_without_duplicate(tmp_path,monkeypatch):
    m=module();client=Client();journals={'STORY':Journal(),'SPOTLIGHT':Journal()}
    # Real publish state transitions; isolated shared visual/approval checks already have dedicated tests.
    monkeypatch.setattr('publishing_v2.bundle_api.check_delivery_approval',lambda media:None)
    monkeypatch.setattr('publishing_v2.challenge_contract.validate_challenge',lambda title,media:None)
    monkeypatch.setattr('publishing_v2.challenge_visual_review.validate_challenge_images',lambda media:None)
    monkeypatch.setattr(m,'require_for_new_delivery',lambda *args:None)
    media=ApprovedMedia([(tmp_path/'final.mp4',b'exact-video')],Path.cwd()/'test-manifest.json',data())
    m.deliver(client,journals,'title',media,DIGEST)
    m.deliver(client,journals,'title',media,DIGEST)
    assert client.sent==['STORY','SPOTLIGHT'] and len(client.uploads)==2

def test_bound_journal_seals_intent_before_create():
    m=module();inner=Journal();j=m.BoundJournal(inner,'sample-package','STORY',DIGEST,DUE)
    j.save({'1':{'status':'SENDING','upload_id':'upload','placement':'STORY'}})
    row=inner.read()['1']
    assert row['media_sha256']==DIGEST and row['package']=='sample-package'
    assert row['reference_key']=='reviewed-challenge-'+DIGEST+'-STORY'
    assert row['not_before']==DUE

def test_provider_reference_key_and_no_archive_are_bound():
    m=module()
    with patch.dict('os.environ',{'BUNDLE_API_KEY':'test','BUNDLE_TEAM_ID':'team'}):client=m.ChallengeClient(DIGEST,datetime(2000,1,1,tzinfo=timezone.utc))
    payload={'data':{'SNAPCHAT':{'type':'SPOTLIGHT','skipSaveToProfile':False}}}
    captured=[]
    def transport(self,path,method='GET',data=None,content_type='application/json'):
        captured.append(json.loads(data));return {'id':'test'}
    with patch('publishing_v2.bundle_api.BundleClient.call',transport):client.call('/post','POST',json.dumps(payload).encode())
    assert captured[0]['referenceKey']=='reviewed-challenge-'+DIGEST+'-SPOTLIGHT'
    assert captured[0]['data']['SNAPCHAT']['skipSaveToProfile'] is True

@pytest.mark.parametrize('name,kind',[('../escape.mp4','file'),('approved/other/video.mp4','file'),('approved/sample-package/manifest.json','file'),('approved/sample-package/video.mp4','symlink'),('approved/sample-package/render.py','file')])
def test_archive_rejects_non_media_and_escaping_members(tmp_path,monkeypatch,name,kind):
    import tarfile,io
    m=module();monkeypatch.chdir(tmp_path);Path('approved').mkdir()
    with tarfile.open('approved/sample-package.tar.xz','w:xz') as archive:
        item=tarfile.TarInfo(name);item.size=1
        if kind=='symlink':item.type=tarfile.SYMTYPE;item.linkname='/tmp/outside'
        archive.addfile(item,io.BytesIO(b'x') if kind=='file' else None)
    seal_archive()
    with pytest.raises(BundleError):m.restore_media('sample-package')
    assert not Path('escape.mp4').exists()

def test_archive_restores_only_bound_media_without_overwriting_metadata(tmp_path,monkeypatch):
    import tarfile,io
    m=module();monkeypatch.chdir(tmp_path);Path('approved/sample-package').mkdir(parents=True)
    with tarfile.open('approved/sample-package.tar.xz','w:xz') as archive:
        item=tarfile.TarInfo('approved/sample-package/video.mp4');item.size=3;archive.addfile(item,io.BytesIO(b'vid'))
    seal_archive()
    before=Path('approved/sample-package/manifest.json').read_bytes()
    m.restore_media('sample-package')
    assert Path('approved/sample-package/video.mp4').read_bytes()==b'vid'
    assert Path('approved/sample-package/manifest.json').read_bytes()==before

@pytest.mark.parametrize('change',[{'status':'PUBLISHING'}, {'deletedAt':'now'}, {'teamId':'wrong'}, {'id':'wrong'}, {'externalData':{'SNAPCHAT':{'status':'PUBLISHED','type':'SPOTLIGHT','sourceUploadIds':['upload-1']}}}])
def test_unconfirmed_receipt_is_not_reported_success(change):
    m=module();client=Client();original=client.call
    client.call=lambda path:original(path)|change
    with pytest.raises(BundleError,match='Unconfirmed'):
        m.verify_receipt(client,{'post_id':'story-post','upload_id':'upload-1'},'STORY',DIGEST)

def test_archive_cannot_follow_preexisting_package_symlink(tmp_path,monkeypatch):
    import tarfile,io
    m=module();monkeypatch.chdir(tmp_path);Path('approved').mkdir();Path('elsewhere').mkdir()
    Path('approved/sample-package').symlink_to(tmp_path/'elsewhere',target_is_directory=True)
    with tarfile.open('approved/sample-package.tar.xz','w:xz') as archive:
        item=tarfile.TarInfo('approved/sample-package/video.mp4');item.size=3;archive.addfile(item,io.BytesIO(b'vid'))
    seal_archive()
    with pytest.raises(BundleError):m.restore_media('sample-package')
    assert not Path('elsewhere/video.mp4').exists()

def test_changed_archive_rejected_even_when_expected_video_is_unchanged(tmp_path,monkeypatch):
    import tarfile,io
    m=module();monkeypatch.chdir(tmp_path);Path('approved/sample-package').mkdir(parents=True)
    archive_path=Path('approved/sample-package.tar.xz')
    def archive(image):
        with tarfile.open(archive_path,'w:xz') as tar:
            for name,raw in [('video.mp4',b'vid'),('image.jpg',image)]:
                item=tarfile.TarInfo('approved/sample-package/'+name);item.size=len(raw);tar.addfile(item,io.BytesIO(raw))
    archive(b'old-image')
    Path('approved/sample-package/manifest.json').write_text(json.dumps({'media':[{'sha256':hashlib.sha256(b'vid').hexdigest()}],'asset_archive':{'path':str(archive_path),'sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest()}}))
    archive(b'new-image')
    with pytest.raises(BundleError,match='archive'):m.restore_media('sample-package')
    assert not Path('approved/sample-package/video.mp4').exists()


def seal_archive():
    path=Path('approved/sample-package.tar.xz')
    target=Path('approved/sample-package/manifest.json')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps({'asset_archive':{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}))

def parted_archive(tmp_path,monkeypatch):
    import tarfile,io
    monkeypatch.chdir(tmp_path);Path('approved/sample-package').mkdir(parents=True)
    base=Path('approved/sample-package.tar.xz')
    with tarfile.open(base,'w:xz') as tar:
        item=tarfile.TarInfo('approved/sample-package/video.mp4');item.size=3;tar.addfile(item,io.BytesIO(b'vid'))
    raw=base.read_bytes();parts=[]
    for i,chunk in enumerate((raw[:len(raw)//2],raw[len(raw)//2:])):
        path=Path(str(base)+f'.part-{i:03d}');path.write_bytes(chunk);parts.append({'path':str(path),'sha256':hashlib.sha256(chunk).hexdigest()})
    spec={'path':str(base),'sha256':hashlib.sha256(raw).hexdigest(),'parts':parts}
    Path('approved/sample-package/manifest.json').write_text(json.dumps({'asset_archive':spec}))
    return base,spec

def test_parts_override_stale_whole_archive(tmp_path,monkeypatch):
    base,spec=parted_archive(tmp_path,monkeypatch);base.write_bytes(b'stale')
    module().restore_media('sample-package')
    assert Path('approved/sample-package/video.mp4').read_bytes()==b'vid'

@pytest.mark.parametrize('fault',['missing','part_hash','combined_hash','order','duplicate','escape','empty','too_many','oversize'])
def test_invalid_parts_fail_before_any_extraction(tmp_path,monkeypatch,fault):
    base,spec=parted_archive(tmp_path,monkeypatch)
    if fault=='missing':Path(spec['parts'][0]['path']).unlink()
    elif fault=='part_hash':Path(spec['parts'][0]['path']).write_bytes(b'bad')
    elif fault=='combined_hash':spec['sha256']='0'*64
    elif fault=='order':spec['parts'].reverse()
    elif fault=='duplicate':spec['parts'][1]=spec['parts'][0]
    elif fault=='escape':spec['parts'][0]['path']='../outside'
    elif fault=='empty':spec['parts']=[]
    elif fault=='too_many':spec['parts']=spec['parts']*65
    else:
        raw=b'x'*600001;Path(spec['parts'][0]['path']).write_bytes(raw);spec['parts'][0]['sha256']=hashlib.sha256(raw).hexdigest()
    Path('approved/sample-package/manifest.json').write_text(json.dumps({'asset_archive':spec}))
    with pytest.raises(BundleError):module().restore_media('sample-package')
    assert not Path('approved/sample-package/video.mp4').exists()

def test_total_part_bytes_are_bounded_before_combining():
    m=module();chunk=b'x'*600000;digest=hashlib.sha256(chunk).hexdigest()
    spec={'path':'approved/sample-package.tar.xz','sha256':'0'*64,'parts':[{'path':f'approved/sample-package.tar.xz.part-{i:03d}','sha256':digest} for i in range(128)]}
    with pytest.raises(BundleError,match='exceeds limit'):
        m.read_archive_bytes('sample-package',spec,reader=lambda path,maximum:chunk)
