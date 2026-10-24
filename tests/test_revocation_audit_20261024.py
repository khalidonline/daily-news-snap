"""Offline regression tests of actual load_package -> publish approval checks.

The contract under test: revocation before create must prevent create.
Only provider/journal boundaries are replaced. No account credentials or APIs.
Run: python -m unittest discover -s tests -p test_revocation_audit_20261024.py -v
"""
import copy
import base64
import hashlib
import json
import socket
from pathlib import Path

import unittest
import tempfile
from unittest.mock import patch
from publishing_v2 import bundle_api as b


def fixture(tmp_path):
    # Deliberately synthetic bytes: this test exercises approval, not rendering.
    raw = b'offline-approval-test-card'
    (tmp_path / 'card.jpg').write_bytes(raw)
    manifest = {'approved': True, 'account': 'executivesaudi',
                'title': 'offline test', 'expires_at': '2999-01-01T00:00:00+00:00',
                'media': [{'path': 'card.jpg', 'kind': 'info',
                           'image': {'license': 'CC0', 'asset_id': 'synthetic'},
                           'sha256': hashlib.sha256(raw).hexdigest()}]}
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    return path, manifest


class Journal:
    def __init__(self, hook):
        self.state = {}
        self.hook = hook

    def read(self):
        self.hook('journal_read')
        return copy.deepcopy(self.state)

    def save(self, state):
        self.state = copy.deepcopy(state)
        if state.get('1', {}).get('status') == 'SENDING':
            self.hook('intent_saved')


class Provider:
    def __init__(self, hook):
        self.hook = hook
        self.creates = []

    def ensure_capacity(self, count):
        assert count == 1
        self.hook('quota_checked')

    def upload(self, item):
        assert item[1] == b'offline-approval-test-card'
        self.hook('upload_returned')
        return 'fake-upload'

    def create(self, title, upload):
        assert upload == 'fake-upload'
        self.creates.append((title, upload))
        return 'fake-post'

    def wait(self, post_id):
        assert post_id == 'fake-post'


def run_revocation(fixture, mode, stage):
    path, data = fixture
    identity, title, media = b.load_package(str(path))
    revoked = []

    def hook(current):
        if current != stage or revoked:
            return
        if mode == 'approved_false':
            path.write_text(json.dumps(dict(data, approved=False)))
        else:
            path.unlink()
        revoked.append(current)

    client, journal = Provider(hook), Journal(hook)
    hook('after_load')
    error = None
    try:
        b.publish(client, journal, title, media)
    except (b.BundleError, OSError) as exc:
        error = type(exc).__name__
    assert revoked == [stage], 'Test did not inject revocation'
    print(json.dumps({'stage': stage, 'mode': mode, 'create_calls': len(client.creates),
                      'journal_status': journal.state.get('1', {}).get('status'),
                      'error': error, 'real_network_calls': 0}))
    assert len(client.creates) == 0, 'Publisher invoked create after revocation'


class RevocationAudit(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for target, replacement in [
            ('pathlib.Path.cwd', lambda: root),
            ('socket.socket.connect', self.deny),
            ('socket.create_connection', self.deny),
            ('publishing_v2.bundle_api.request', self.deny),
        ]:
            patcher = patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.fixture = fixture(root)
        environment = patch.dict('os.environ', {'GITHUB_ACTIONS': 'false'})
        environment.start()
        self.addCleanup(environment.stop)

    @staticmethod
    def deny(*args, **kwargs):
        raise AssertionError('NETWORK_FORBIDDEN_IN_AUDIT')

    def test_control_revoked_before_load_is_rejected(self):
        path, data = self.fixture
        path.write_text(json.dumps(dict(data, approved=False)))
        with self.assertRaisesRegex(b.BundleError, 'approved'):
            b.load_package(str(path))

    def test_control_valid_approval_and_resume(self):
        path, _ = self.fixture
        _, title, media = b.load_package(str(path))
        client, journal = Provider(lambda _: None), Journal(lambda _: None)
        b.publish(client, journal, title, media)
        b.publish(client, journal, title, media)
        self.assertEqual(len(client.creates), 1)
        self.assertEqual(journal.state['1']['status'], 'POSTED')

    def test_remote_revocation_overrides_unchanged_checkout(self):
        path, data = self.fixture
        _, title, media = b.load_package(str(path))
        client, journal = Provider(lambda _: None), Journal(lambda _: None)
        response = {'encoding': 'base64', 'content': base64.b64encode(
            json.dumps(dict(data, approved=False)).encode()).decode()}
        with patch.dict('os.environ', {'GITHUB_ACTIONS': 'true',
                'GITHUB_REPOSITORY': 'khalidonline/daily-news-snap', 'GITHUB_TOKEN': 'test'}), \
                patch.object(b, 'request', return_value=response):
            with self.assertRaises(b.BundleError):
                b.publish(client, journal, title, media)
        self.assertEqual(client.creates, [])
        self.assertEqual(json.loads(path.read_text())['approved'], True)

    def test_remote_failure_never_falls_back_to_checkout(self):
        path, _ = self.fixture
        _, title, media = b.load_package(str(path))
        client, journal = Provider(lambda _: None), Journal(lambda _: None)
        with patch.dict('os.environ', {'GITHUB_ACTIONS': 'true',
                'GITHUB_REPOSITORY': 'khalidonline/daily-news-snap', 'GITHUB_TOKEN': 'test'}), \
                patch.object(b, 'request', side_effect=b.HTTPFailure(503)):
            with self.assertRaises(b.BundleError):
                b.publish(client, journal, title, media)
        self.assertEqual(client.creates, [])

    def test_remote_valid_approval_allows_delivery(self):
        path, data = self.fixture
        _, title, media = b.load_package(str(path))
        client, journal = Provider(lambda _: None), Journal(lambda _: None)
        def remote(url, headers):
            self.assertIn('/contents/manifest.json?ref=main&', url)
            return {'encoding': 'base64', 'content': base64.b64encode(
                json.dumps(data).encode()).decode()}
        with patch.dict('os.environ', {'GITHUB_ACTIONS': 'true',
                'GITHUB_REPOSITORY': 'khalidonline/daily-news-snap', 'GITHUB_TOKEN': 'test'}), \
                patch.object(b, 'request', side_effect=remote):
            b.publish(client, journal, title, media)
        self.assertEqual(journal.state['1']['status'], 'POSTED')
        self.assertEqual(len(client.creates), 1)

    def test_expired_or_modified_approval_blocks_delivery(self):
        path, data = self.fixture
        _, title, media = b.load_package(str(path))
        for change in [{'expires_at': '2000-01-01T00:00:00+00:00'},
                       {'title': 'unreviewed title'}, {'account': 'other'}]:
            path.write_text(json.dumps(dict(data, **change)))
            client, journal = Provider(lambda _: None), Journal(lambda _: None)
            with self.assertRaises(b.BundleError):
                b.publish(client, journal, title, media)
            self.assertEqual(client.creates, [])

    def test_revocation_between_cards_preserves_first_receipt(self):
        path, data = self.fixture
        raw = b'second synthetic card'
        (path.parent / 'second.jpg').write_bytes(raw)
        data['media'].append({'path': 'second.jpg', 'kind': 'info',
            'image': {'license': 'CC0', 'asset_id': 'second'},
            'sha256': hashlib.sha256(raw).hexdigest()})
        path.write_text(json.dumps(data))
        _, title, media = b.load_package(str(path))
        client, journal = Provider(lambda _: None), Journal(lambda _: None)
        client.ensure_capacity = lambda count: self.assertEqual(count, 2)
        def stop_after_first(post_id):
            self.assertEqual(post_id, 'fake-post')
            path.write_text(json.dumps(dict(data, approved=False)))
        client.wait = stop_after_first
        with self.assertRaises(b.BundleError):
            b.publish(client, journal, title, media)
        self.assertEqual(len(client.creates), 1)
        self.assertEqual(journal.state['1']['status'], 'POSTED')
        self.assertNotIn('2', journal.state)

    def test_group_revocation_after_intent_blocks_create(self):
        path, data = self.fixture
        _, title, single = b.load_package(str(path))
        media = b.ApprovedMedia([single[0], single[0]], path, data)
        def stop(stage):
            if stage == 'intent_saved':
                path.write_text(json.dumps(dict(data, approved=False)))
        client, journal = Provider(stop), Journal(stop)
        uploads = iter(['u1', 'u2'])
        client.upload = lambda item: next(uploads)
        client.create_group = lambda *args: self.fail('Group created after revocation')
        with self.assertRaises(b.BundleError):
            b.publish_group(client, journal, title, media, 'test-identity')
        self.assertNotIn('post_id', journal.state['_group'])


def make_test(mode, stage):
    def test(self):
        run_revocation(self.fixture, mode, stage)
    return test


for mode in ['approved_false', 'manifest_deleted']:
    for stage in ['after_load', 'journal_read', 'quota_checked', 'upload_returned', 'intent_saved']:
        setattr(RevocationAudit, 'test_' + mode + '_' + stage, make_test(mode, stage))
