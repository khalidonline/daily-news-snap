import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from publishing_v2.bundle_api import load_package, BundleError
from publishing_v2.autopilot.runtime import publish_package

class Client:
    def __init__(self): self.uploaded=[]
    def check(self): pass
    def upload(self, item): self.uploaded.append(item[1]); return str(len(self.uploaded))
    def create(self, title, upload): return 'post-'+upload
    def wait(self, post): pass
class Journal:
    def __init__(self): self.state={}
    def read(self): return copy.deepcopy(self.state)
    def save(self, state): self.state=copy.deepcopy(state)

class PublicationSelectionTests(unittest.TestCase):
    def fixture(self, root):
        paths=[]
        for i in range(4):
            path=Path(root)/f'{i}.jpg'; path.write_bytes(f'card {i}'.encode()); paths.append(path)
        cards=[{'kind':kind,'image':{'license':'CC0','asset_id':str(i)}}
               for i,kind in enumerate(['info','story','story','credits'])]
        return {'title':'test','expires_at':'2999-01-01T00:00:00+00:00','cards':cards},paths

    def test_auto_only_sends_editorial_cards_in_order_and_keeps_review(self):
        with tempfile.TemporaryDirectory() as root:
            package,paths=self.fixture(root); original=copy.deepcopy(package)
            client,journal=Client(),Journal()
            receipt=publish_package(package,paths,client=client,journal_factory=lambda _:journal)
            self.assertEqual(client.uploaded,[b'card 0',b'card 1',b'card 2'])
            self.assertEqual(receipt['card_count'],3)
            self.assertEqual(package,original)

    def test_video_with_credit_frame_never_uploads(self):
        with tempfile.TemporaryDirectory() as root:
            package,paths=self.fixture(root)
            raw=b'old video with credits';(Path(root)/'story.mp4').write_bytes(raw)
            package['delivery']={'kind':'video','filename':'story.mp4','duration_seconds':45,
                'sha256':hashlib.sha256(raw).hexdigest(),
                'frame_sha256':[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]}
            client=Client()
            with self.assertRaisesRegex(ValueError,'review_video_not_publishable'):
                publish_package(package,paths,client=client,journal_factory=lambda _:Journal())
            self.assertEqual(client.uploaded,[])

    def test_attribution_is_not_silently_removed_with_credits(self):
        with tempfile.TemporaryDirectory() as root:
            package,paths=self.fixture(root); package['cards'][0]['image']['license']='CC BY 2.0'
            with self.assertRaisesRegex(ValueError,'public_attribution_required'):
                publish_package(package,paths,client=Client())

    def test_manual_manifest_excludes_review_card_and_requires_explicit_kinds(self):
        with tempfile.TemporaryDirectory() as root,patch('pathlib.Path.cwd',return_value=Path(root)):
            package,paths=self.fixture(root)
            manifest={'approved':True,'account':'executivesaudi','title':'test',
                'expires_at':package['expires_at'],'media':[
                    {'path':p.name,'kind':c['kind'],'image':c['image'],
                     'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                    for c,p in zip(package['cards'],paths)]}
            target=Path(root)/'manifest.json'; target.write_text(json.dumps(manifest))
            _,_,media=load_package('manifest.json')
            self.assertEqual([b for _,b in media],[b'card 0',b'card 1',b'card 2'])
            del manifest['media'][0]['kind'];target.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(BundleError,'explicit_media_kind_required'):
                load_package('manifest.json')
