import json
from pathlib import Path
import pytest
from publishing_v2.bundle_api import BundleClient, BundleError, publish
from tests.test_v2_bundle import Client, Journal
from publishing_v2.bundle_api import load_package

def test_approved_video_uses_spotlight_and_reconciles_without_repeat(monkeypatch):
    # This test uses an in-memory client/journal; live revocation belongs to
    # the real delivery step, whose GITHUB_ACTIONS guard remains enabled.
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    path = Path('approved/wheels-video-20261025/manifest.json')
    if not path.exists(): pytest.skip('Owner-approved integration fixture missing')
    _, title, media = load_package(str(path))
    class SpotlightClient(Client):
        def create_spotlight(self, title, upload):
            self.sent.append(('SPOTLIGHT', upload)); return 'spotlight-post'
        def create(self, title, upload):
            raise AssertionError('Wrong destination')
    client, journal = SpotlightClient(), Journal()
    publish(client, journal, title, media, placement='SPOTLIGHT')
    publish(client, journal, title, media, placement='SPOTLIGHT')
    assert client.sent == [('SPOTLIGHT', 'upload')]
    assert journal.state['1'] == {'status':'POSTED','upload_id':'upload',
                                  'placement':'SPOTLIGHT','post_id':'spotlight-post'}
    with pytest.raises(BundleError, match='destination mismatch'):
        publish(client, journal, title, media, placement='STORY')

def test_spotlight_payload_does_not_use_story_duration():
    client = object.__new__(BundleClient)
    client.team = 'team'
    payloads = []
    def transport(path, method, data):
        payloads.append(json.loads(data)); return {'id':'new-post'}
    client.call = transport
    assert client.create_spotlight('توقع السعر', 'upload') == 'new-post'
    snap = payloads[0]['data']['SNAPCHAT']
    assert snap == {'type':'SPOTLIGHT', 'uploadIds':['upload'],
                    'description':'توقع السعر', 'locale':'ar_SA', 'skipSaveToProfile':False}

def test_unapproved_spotlight_never_uploads():
    client, journal = Client(), Journal()
    with pytest.raises(BundleError, match='destination'):
        publish(client, journal, 'title', [(Path('a.png'),b'png')], placement='SPOTLIGHT')
    assert not client.sent

def test_story_receipt_cannot_be_mistaken_for_spotlight():
    client, journal = Client(), Journal()
    journal.state={'1':{'status':'POSTED','post_id':'old','placement':'STORY'}}
    with pytest.raises(BundleError):
        publish(client, journal, 'title', [(Path('a.mp4'),b'mp4')], placement='SPOTLIGHT')
    assert not client.sent
