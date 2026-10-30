"""Owner's six-file archive exception must never become a general bypass."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from publishing_v2.bundle_api import ApprovedMedia, BundleError
from publishing_v2.design_contract import validate_design, SETTINGS

class ArchiveExceptionTest(unittest.TestCase):
    def setUp(self):
        self.clock=patch('publishing_v2.design_contract.datetime', create=True)
        clock=self.clock.start();self.addCleanup(self.clock.stop)
        clock.now.return_value=datetime(2026,10,30,20,tzinfo=timezone.utc)
        clock.fromisoformat.side_effect=datetime.fromisoformat
        self.root=Path.cwd().resolve()
        self.manifest=json.loads(Path('approved/oxford-20261027/manifest.json').read_text())
        self.manifest.update(approved_destinations=['SAVED_STORY'], archive_exception='khalid-six-archives-20261030', expires_at='2026-10-30T23:59:00+00:00')
        settings=SETTINGS.read_bytes()
        self.report={'version':1,'settings_revision':json.loads(settings)['canonical_reference']['revision'],
            'settings_sha256':hashlib.sha256(settings).hexdigest(),'destinations':['SAVED_STORY'],
            'archive_exception':'khalid-six-archives-20261030',
            'waived_checks':['current_template_design_review']}

    def media(self, data=None):
        d=data or self.manifest
        return ApprovedMedia([(self.root/f['path'],(self.root/f['path']).read_bytes()) for f in d['media']],
            self.root/'approved/archive-six-20261030/oxford/manifest.json',d)

    def test_all_six_exact_posted_files_allowed_as_explicit_exception_not_design_pass(self):
        for name in ['rice-20261026','oxford-20261027','global-entry-20261028','youtube-shopping-20261028','shubaily-20261029','twins-20261029']:
            with self.subTest(name=name):
                d=json.loads((self.root/'approved'/name/'manifest.json').read_text())
                d.update({k:self.manifest[k] for k in ['approved_destinations','archive_exception','expires_at']})
                try: result=validate_design(self.media(d),self.report,'SAVED_STORY')
                except BundleError as e:self.fail(str(e))
                self.assertEqual(result['status'],'owner_authorized_archive_exception')

    def test_exception_cannot_republish_story_or_spotlight(self):
        for placement in ['STORY','SPOTLIGHT']:
            r=copy.deepcopy(self.report);r['destinations']=[placement]
            with self.assertRaises(BundleError):validate_design(self.media(),r,placement)

    def test_rejects_changed_bytes_and_extra_media(self):
        media=self.media();p,b=media[0];media[0]=(p,b+b'x')
        with self.assertRaises(BundleError):validate_design(media,self.report,'SAVED_STORY')
        media=self.media();media.append(media[0])
        with self.assertRaises(BundleError):validate_design(media,self.report,'SAVED_STORY')

    def test_rejects_challenge_and_unlisted_starbucks(self):
        d=copy.deepcopy(self.manifest);d['content_type']='challenge'
        with self.assertRaises(BundleError):validate_design(self.media(d),self.report,'SAVED_STORY')
        d=json.loads(Path('approved/starbucks-20261030/manifest.json').read_text())
        d.update({k:self.manifest[k] for k in ['approved_destinations','archive_exception','expires_at']})
        with self.assertRaises(BundleError):validate_design(self.media(d),self.report,'SAVED_STORY')

    def test_rejects_missing_approval_and_expiry_extension(self):
        for change in [{'approved':False},{'archive_exception':None},{'expires_at':'2026-11-10T00:00:00+00:00'}]:
            d=copy.deepcopy(self.manifest);d.update(change)
            with self.assertRaises(BundleError):validate_design(self.media(d),self.report,'SAVED_STORY')

    def test_exception_expires(self):
        with patch('publishing_v2.design_contract.datetime') as clock:
            clock.now.return_value=datetime(2026,10,31,1,tzinfo=timezone.utc)
            clock.fromisoformat.side_effect=datetime.fromisoformat
            with self.assertRaises(BundleError):validate_design(self.media(),self.report,'SAVED_STORY')
