import hashlib
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import pytest

NOW=datetime(2026,11,17,7,tzinfo=timezone.utc)
DUE='2026-11-17T10:00:00Z'
PACKAGE='reviewed-sample'
REQUEST='.github/challenge-publish-request.json'

def module():return importlib.import_module('publishing_v2.publication_request')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],stderr=subprocess.PIPE).decode().strip()
def write(path,data):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(json.dumps(data).encode() if isinstance(data,dict) else data)

@pytest.fixture
def repo(tmp_path,monkeypatch):
 monkeypatch.chdir(tmp_path);git('init','-q');git('config','user.name','Test');git('config','user.email','test@example.com')
 manifest={'format':'reviewed-challenge-video-v1','content_type':'challenge','approved':True,'approved_destinations':['STORY','SPOTLIGHT'],'not_before':DUE,'expires_at':'2026-11-17T23:59:59Z','media':[{'sha256':'a'*64}]}
 files={'manifest.json':manifest,'design-review.json':{'review':'fixture'},'source-approval.json':{'source':'fixture'}}
 for name,data in files.items():write(f'approved/{PACKAGE}/{name}',data)
 write(f'approved/{PACKAGE}.tar.xz',b'fixture archive; real decoding belongs to delivery validation')
 git('add','.');git('commit','-qm','base');before=git('rev-parse','HEAD')
 request={'version':1,'action':'validate','package':PACKAGE,'expected_video_sha256':'a'*64,'not_before':DUE}
 for field,path in [('manifest_sha256',f'approved/{PACKAGE}/manifest.json'),('design_review_sha256',f'approved/{PACKAGE}/design-review.json'),('source_manifest_sha256',f'approved/{PACKAGE}/source-approval.json'),('media_archive_sha256',f'approved/{PACKAGE}.tar.xz')]:request[field]=sha(Path(path).read_bytes())
 return tmp_path,before,request

def commit_event(before,request,*,both=False):
 write(REQUEST,request)
 if both:write('.github/information-publish-request.json',{'fixture':'simultaneous'})
 git('add','.');git('commit','-qm','request')
 return {'ref':'refs/heads/main','repository':{'full_name':'khalidonline/daily-news-snap'},'deleted':False,'forced':False,'before':before,'after':git('rev-parse','HEAD')}

def test_validate_request_is_bound_and_allowed_before_due(repo):
 root,before,request=repo;event=commit_event(before,request)
 result=module().resolve_push(root,event,NOW)
 assert result=={'mode':'reviewed-challenge','package':PACKAGE,'challenge_action':'validate','expected_video_sha256':'a'*64,'not_before':DUE}

def test_publish_request_before_due_is_blocked(repo):
 root,before,request=repo;request['action']='publish';event=commit_event(before,request)
 with pytest.raises(ValueError,match='before'):module().resolve_push(root,event,NOW)

def test_publish_request_at_due_is_resolved_not_executed(repo):
 root,before,request=repo;request['action']='publish';event=commit_event(before,request)
 result=module().resolve_push(root,event,datetime(2026,11,17,10,tzinfo=timezone.utc))
 assert result['challenge_action']=='publish' and result['expected_video_sha256']=='a'*64

@pytest.mark.parametrize('change',[{'action':None},{'action':'retry'},{'expected_video_sha256':'b'*64},{'not_before':'2026-11-17T09:00:00Z'},{'manifest_sha256':'0'*64},{'media_archive_sha256':'0'*64},{'package':'../other'}])
def test_request_rejects_missing_or_changed_binding(repo,change):
 root,before,request=repo;request.update(change);event=commit_event(before,request)
 with pytest.raises(ValueError):module().resolve_push(root,event,NOW)

def test_both_request_types_in_one_push_are_rejected(repo):
 root,before,request=repo;event=commit_event(before,request,both=True)
 with pytest.raises(ValueError,match='one'):module().resolve_push(root,event,NOW)

@pytest.mark.parametrize('path',[REQUEST,f'approved/{PACKAGE}/manifest.json',f'approved/{PACKAGE}/design-review.json',f'approved/{PACKAGE}.tar.xz'])
def test_modified_checkout_is_not_event_commit(repo,path):
 root,before,request=repo;event=commit_event(before,request);Path(path).write_bytes(b'changed')
 with pytest.raises(ValueError):module().resolve_push(root,event,NOW)

def test_information_request_keeps_original_resolver(repo,monkeypatch):
 root,before,request=repo;write('.github/information-publish-request.json',{'fixture':True});git('add','.');git('commit','-qm','information');event={'ref':'refs/heads/main','repository':{'full_name':'khalidonline/daily-news-snap'},'deleted':False,'forced':False,'before':before,'after':git('rev-parse','HEAD')}
 import publishing_v2.information_request as information
 monkeypatch.setattr(information,'resolve_push',lambda r,e,n:r/'approved'/'information-fixture')
 assert module().resolve_push(root,event,NOW)=={'mode':'prepared-information','package':'information-fixture'}

@pytest.mark.parametrize('retained_path',[REQUEST,'.github/information-publish-request.json'])
def test_retained_request_does_not_authorize_later_ordinary_push(repo,retained_path):
 root,before,request=repo;write(retained_path,request);git('add','.');git('commit','-qm','retained request')
 before=git('rev-parse','HEAD');write('readme.txt',b'unrelated');git('add','.');git('commit','-qm','ordinary')
 event={'ref':'refs/heads/main','repository':{'full_name':'khalidonline/daily-news-snap'},'deleted':False,'forced':False,'before':before,'after':git('rev-parse','HEAD')}
 with pytest.raises(ValueError,match='one'):module().resolve_push(root,event,NOW)

def commit_part_request(repo):
 root,before,request=repo;archive=Path(f'approved/{PACKAGE}.tar.xz');raw=archive.read_bytes();parts=[]
 for i,chunk in enumerate((raw[:12],raw[12:])):
  path=Path(str(archive)+f'.part-{i:03d}');path.write_bytes(chunk);parts.append({'path':str(path),'sha256':sha(chunk)})
 manifest_path=Path(f'approved/{PACKAGE}/manifest.json');manifest=json.loads(manifest_path.read_text());manifest['asset_archive']={'path':str(archive),'sha256':sha(raw),'parts':parts};write(manifest_path,manifest);request['manifest_sha256']=sha(manifest_path.read_bytes());archive.unlink()
 return root,commit_event(before,request),parts

def test_part_request_uses_committed_parts_without_whole_blob(repo):
 root,event,parts=commit_part_request(repo)
 assert module().resolve_push(root,event,NOW)['challenge_action']=='validate'

def test_local_part_differing_from_event_commit_is_rejected(repo):
 root,event,parts=commit_part_request(repo);Path(parts[0]['path']).write_bytes(b'changed')
 with pytest.raises(ValueError):module().resolve_push(root,event,NOW)
