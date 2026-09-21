"""Approved original illustrations retain exact bytes without granting agent authority."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from publishing_v2.bundle_api import BundleError, load_package, main
from publishing_v2.publication import publication_indices


class OwnerDesignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cwd = patch('pathlib.Path.cwd', return_value=self.root)
        self.cwd.start(); self.addCleanup(self.cwd.stop)
        self.data = {'format': 'owner-generated-design-v1', 'approved': True,
                     'account': 'executivesaudi', 'title': 'Approved original design',
                     'expires_at': '2999-01-01T00:00:00+00:00',
                     'owner_review': {'reference': 'chat:2026-09-21:publish',
                                      'reviewed_at': '2026-09-21T08:00:00+00:00',
                                      'approved_media_sha256': []}, 'media': []}
        self.raw = []
        for i, color in enumerate(['red', 'green', 'blue']):
            out = io.BytesIO(); Image.new('RGB', (576,1024), color).save(out,'PNG')
            raw = out.getvalue(); self.raw.append(raw)
            (self.root / f'{i}.png').write_bytes(raw)
            sha = hashlib.sha256(raw).hexdigest()
            self.data['owner_review']['approved_media_sha256'].append(sha)
            self.data['media'].append({'path': f'{i}.png', 'sha256':sha,
                'kind': 'info' if i in (0,2) else 'story',
                'provenance': {'provider':'openai_imagegen', 'library_file_id':'libfile_'+str(i)*32,
                    'usage':'illustration', 'third_party_assets':False}})

    def write(self):
        (self.root/'manifest.json').write_text(json.dumps(self.data))

    def test_exact_bytes_order_and_identity_survive_owner_design_loading(self):
        self.write()
        identity, title, media = load_package('manifest.json')
        self.assertEqual([b for _, b in media], self.raw)
        # Same existing delivery identity across filenames and titles.
        self.data['title']='renamed'; self.write()
        self.assertEqual(load_package('manifest.json')[0], identity)

    def test_owner_review_binds_order_not_just_boolean_approval(self):
        self.data['media'].reverse(); self.write()
        with self.assertRaisesRegex(BundleError,'owner_review_media_mismatch'):
            load_package('manifest.json')

    def test_tamper_missing_provenance_or_unreviewed_external_assets_fail(self):
        original = copy.deepcopy(self.data)
        for change in ['hash','provenance','third_party','approval','reference','expired','credits']:
            with self.subTest(change=change):
                self.data=copy.deepcopy(original)
                if change=='hash': self.data['media'][0]['sha256']='0'*64
                if change=='provenance': del self.data['media'][0]['provenance']
                if change=='third_party': self.data['media'][0]['provenance']['third_party_assets']=True
                if change=='approval': self.data['approved']=False
                if change=='reference': self.data['owner_review']['reference']=''
                if change=='expired': self.data['expires_at']='2020-01-01T00:00:00+00:00'
                if change=='credits': self.data['media'][0]['kind']='credits'
                self.write()
                with self.assertRaises(BundleError): load_package('manifest.json')

    def test_invalid_image_cannot_pass_even_with_matching_hash_and_review(self):
        raw=b'not a png'; (self.root/'0.png').write_bytes(raw)
        sha=hashlib.sha256(raw).hexdigest()
        self.data['media'][0]['sha256']=sha
        self.data['owner_review']['approved_media_sha256'][0]=sha
        self.write()
        with self.assertRaisesRegex(BundleError,'invalid_owner_design_image'):
            load_package('manifest.json')

    def test_original_bytes_changed_after_approval_are_rejected(self):
        self.write(); (self.root/'0.png').write_bytes(self.raw[1])
        with self.assertRaisesRegex(BundleError,'Media changed after approval'):
            load_package('manifest.json')

    def test_path_escape_and_duplicate_provenance_are_rejected(self):
        self.data['media'][0]['path']='../outside.png'; self.write()
        with self.assertRaises(BundleError): load_package('manifest.json')
        self.data['media'][0]['path']='0.png'
        self.data['media'][1]['provenance']=self.data['media'][0]['provenance']; self.write()
        with self.assertRaisesRegex(BundleError,'duplicate_generated_asset'):
            load_package('manifest.json')

    def test_autonomous_publication_does_not_accept_owner_provenance(self):
        with self.assertRaisesRegex(ValueError,'public_attribution_required'):
            publication_indices(self.data['media'])

    def test_validate_has_no_credentials_network_or_journal_side_effects(self):
        self.write()
        with patch('sys.argv',['bundle_api','validate','--manifest','manifest.json']), \
             patch('publishing_v2.bundle_api.BundleClient',side_effect=AssertionError('network client')), \
             patch('publishing_v2.bundle_api.GitHubJournal',side_effect=AssertionError('journal')), \
             patch('sys.stdout',new_callable=io.StringIO) as output:
            main()
        result=json.loads(output.getvalue())
        self.assertEqual(result['status'],'validated_not_published')
        self.assertEqual(result['card_count'],3)

if __name__=='__main__': unittest.main()
