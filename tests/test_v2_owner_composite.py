"""Owner-approved external media must be supported without losing approval binding."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from publishing_v2.bundle_api import BundleError, load_package
from publishing_v2.publication import publication_indices


class OwnerCompositeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        p = patch('pathlib.Path.cwd', return_value=self.root)
        p.start(); self.addCleanup(p.stop)
        Image.new('RGB', (1080, 1920), 'ivory').save(self.root/'card.png')
        Image.new('RGB', (80, 100), 'navy').save(self.root/'source.png')
        self.raw = (self.root/'card.png').read_bytes()
        self.sha = hashlib.sha256(self.raw).hexdigest()
        self.source_sha = hashlib.sha256((self.root/'source.png').read_bytes()).hexdigest()
        self.data = {'format':'owner-reviewed-composite-v1', 'approved':True,
            'account':'executivesaudi', 'title':'Owner approved composite',
            'expires_at':'2999-01-01T00:00:00+00:00',
            'owner_review':{'reference':'Khalid selected portrait and authorized publication',
                'reviewed_at':'2026-10-25T08:00:00+00:00',
                'approved_media_sha256':[self.sha], 'approved_source_sha256':[self.source_sha]},
            'media':[{'kind':'info','path':'card.png','sha256':self.sha,
                'provenance':{'usage':'mixed_editorial_composite','generated_components':True},
                'source_assets':[{'path':'source.png','sha256':self.source_sha,
                    'source_url':'https://example.org/official-history',
                    'description':'Founder portrait selected by owner',
                    'rights_status':'owner_accepted_editorial_use',
                    'owner_reference':'Khalid uploaded exact portrait and requested publication'}]}]}

    def load(self):
        (self.root/'manifest.json').write_text(json.dumps(self.data))
        return load_package('manifest.json')

    def test_reviewed_mixed_card_keeps_exact_bytes_and_revocable_approval(self):
        identity, title, media = self.load()
        self.assertEqual(media[0][1], self.raw)
        self.data['approved'] = False
        (self.root/'manifest.json').write_text(json.dumps(self.data))
        with self.assertRaisesRegex(BundleError, 'Approval revoked'):
            media.check_approval()

    def test_sources_are_required_reviewed_and_bound_to_bytes(self):
        original = copy.deepcopy(self.data)
        for defect in ['missing','hash','approval','url','rights','reference','escape','empty_review']:
            with self.subTest(defect=defect):
                self.data=copy.deepcopy(original)
                source=self.data['media'][0]['source_assets'][0]
                if defect=='missing': self.data['media'][0]['source_assets']=[]
                if defect=='hash': source['sha256']='0'*64
                if defect=='approval': self.data['owner_review']['approved_source_sha256']=[]
                if defect=='url': source['source_url']='file:///private'
                if defect=='rights': source['rights_status']='unknown'
                if defect=='reference': source['owner_reference']=''
                if defect=='escape': source['path']='../source.png'
                if defect=='empty_review': self.data['owner_review']['reference']=''
                with self.assertRaises(BundleError): self.load()

    def test_wrong_dimensions_and_media_tampering_rejected(self):
        Image.new('RGB',(941,1672),'ivory').save(self.root/'card.png')
        digest=hashlib.sha256((self.root/'card.png').read_bytes()).hexdigest()
        self.data['media'][0]['sha256']=digest
        self.data['owner_review']['approved_media_sha256']=[digest]
        with self.assertRaises(BundleError): self.load()

    def test_autonomous_route_still_rejects_manual_composite(self):
        with self.assertRaises(ValueError): publication_indices(self.data['media'])

if __name__=='__main__': unittest.main()
