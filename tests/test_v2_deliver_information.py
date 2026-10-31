import hashlib
import importlib
import json
import subprocess

import pytest
from test_v2_prepared_information import package
from publishing_v2.prepared_information import prepare


def module():
    assert importlib.util.find_spec('publishing_v2.deliver_information'), 'delivery module missing'
    return importlib.import_module('publishing_v2.deliver_information')


@pytest.fixture
def ready(package):
    manifest=package/'manifest.json'
    d=json.loads(manifest.read_text());d['media'][0]['kind']='info'
    manifest.write_text(json.dumps(d))
    identity=hashlib.sha256(('executivesaudi:'+d['media'][0]['sha256']).encode()).hexdigest()
    a={'approved':False,'account':'executivesaudi','empty_profile_confirmation':'confirmed',
       'expires_at':'2099-01-01T00:00:00Z','manifest':'approved/example/manifest.json',
       'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'identity':identity,'title':'example'}
    archive=package/'archive-approval.json';archive.write_text(json.dumps(a))
    prepare(package)
    d['approved']=True;manifest.write_text(json.dumps(d))
    a.update(approved=True,manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
    archive.write_text(json.dumps(a))
    return package


@pytest.fixture
def boundary(monkeypatch):
    m=module();calls=[]
    def run(args,check):
        calls.append(args)
    monkeypatch.setattr(m.subprocess,'run',run)
    return m,calls


def test_order_and_timings(ready,boundary):
    m,calls=boundary
    result=m.deliver(ready)
    assert [c[2] for c in calls]==['publishing_v2.bundle_api','publishing_v2.bundle_api','publishing_v2.saved_story_api']
    assert calls[0][3]=='validate' and calls[1][3]=='publish'
    assert result['STORY']=='CONFIRMED_BY_PUBLISHER'
    assert result['SAVED_STORY']=='CONFIRMED_BY_PUBLISHER'
    assert set(result['seconds'])=={'preflight','story','archive','total'}


@pytest.mark.parametrize('fault',['missing','draft','changed','expired','wrong_manifest'])
def test_archive_preflight_blocks_story(ready,boundary,fault):
    m,calls=boundary;p=ready/'archive-approval.json'
    if fault=='missing':p.unlink()
    elif fault=='changed':(ready/'card.png').write_bytes(b'changed')
    else:
        a=json.loads(p.read_text())
        a.update({'approved':False} if fault=='draft' else {'expires_at':'2000-01-01T00:00:00Z'} if fault=='expired' else {'manifest':'approved/other/manifest.json'})
        p.write_text(json.dumps(a))
        if fault in ('expired','wrong_manifest'):prepare(ready)
    with pytest.raises((ValueError,RuntimeError,OSError)):m.deliver(ready)
    assert calls==[]


def test_story_failure_stops_archive(ready,boundary,monkeypatch):
    m,calls=boundary
    def run(args,check):
        calls.append(args)
        if args[3]=='publish':raise subprocess.CalledProcessError(1,args)
    monkeypatch.setattr(m.subprocess,'run',run)
    with pytest.raises(m.DeliveryFailure) as err:m.deliver(ready)
    assert len(calls)==2
    assert err.value.result['SAVED_STORY']=='NOT_STARTED'
    assert err.value.result['STORY']=='UNCONFIRMED_CHECK_RECEIPTS'


def test_archive_failure_and_retry_keep_identity(ready,boundary,monkeypatch):
    from publishing_v2.bundle_api import publish, BundleError
    from publishing_v2.saved_story_api import save_story
    from test_v2_bundle import Client as StoryClient, Journal
    from test_v2_saved_story_api import Client as ArchiveClient
    m,calls=boundary
    story,archive=StoryClient(),ArchiveClient()
    story_receipts,archive_receipts=Journal(),Journal()
    archive.timeout=True
    # Keep actual publishing and journal reconciliation logic; replace only
    # subprocess launching and external provider/storage with in-memory fakes.
    def run(args,check):
        try:
            if args[2]=='publishing_v2.bundle_api' and args[3]=='publish':
                publish(story,story_receipts,'example',['card'])
            if args[2]=='publishing_v2.saved_story_api':
                save_story(archive,archive_receipts,'identity','example',
                           [story_receipts.read()['1']['upload_id']])
        except BundleError as exc:
            raise subprocess.CalledProcessError(1,args) from exc
    monkeypatch.setattr(m.subprocess,'run',run)
    with pytest.raises(m.DeliveryFailure) as err:m.deliver(ready)
    assert err.value.result['STORY']=='CONFIRMED_BY_PUBLISHER'
    assert err.value.result['SAVED_STORY']=='UNCONFIRMED_CHECK_RECEIPTS'
    # First create was ambiguous: retry must stop without a second create.
    archive.timeout=False
    with pytest.raises(m.DeliveryFailure):m.deliver(ready)
    assert len(story.sent)==1 and archive.created==1
    # Provider inventory later discovers the first archive; reconcile it.
    archive.found=['id1']
    result=m.deliver(ready)
    assert len(story.sent)==1 and archive.created==1
    assert archive_receipts.read()['status']=='POSTED'
    assert result['SAVED_STORY']=='CONFIRMED_BY_PUBLISHER'
