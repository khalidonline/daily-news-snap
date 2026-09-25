import copy
import unittest
from datetime import datetime, timezone
from publishing_v2.bundle_api import BundleError, HTTPFailure, publish


class Journal:
    def __init__(self, state=None): self.state = state or {}
    def read(self): return copy.deepcopy(self.state)
    def save(self, state): self.state = copy.deepcopy(state)


class RecoveryTests(unittest.TestCase):
    def test_create_403_is_recorded_without_allowing_another_create(self):
        class Client:
            calls = 0
            def ensure_capacity(self, count): pass
            def upload(self, item): return 'upload-1'
            def create(self, title, upload):
                self.calls += 1
                raise HTTPFailure(403)
        client, journal = Client(), Journal()
        with self.assertRaises(HTTPFailure): publish(client, journal, 'title', ['image'])
        self.assertEqual(journal.state['1'].get('error', {}).get('http_status'), 403)
        self.assertEqual(journal.state['1']['status'], 'SENDING')
        with self.assertRaises(BundleError): publish(client, journal, 'title', ['image'])
        self.assertEqual(client.calls, 1)

    def test_rerender_cannot_skip_uncertain_predecessor(self):
        import publishing_v2.bundle_api as api
        self.assertTrue(hasattr(api, 'check_predecessors'), 'missing cross-version recovery guard')
        previous = Journal({'1': {'status': 'SENDING', 'upload_id': 'old-upload'}})
        with self.assertRaises(BundleError):
            api.check_predecessors(['a'*64], lambda key: previous)

    def test_missing_predecessor_state_is_not_proof_of_no_post(self):
        import publishing_v2.bundle_api as api
        self.assertTrue(hasattr(api, 'check_predecessors'), 'missing cross-version recovery guard')
        with self.assertRaises(BundleError):
            api.check_predecessors(['a'*64], lambda key: Journal())

    def test_documented_reconciliation_is_required_even_for_posted_predecessor(self):
        import publishing_v2.bundle_api as api
        self.assertTrue(hasattr(api, 'check_predecessors'), 'missing cross-version recovery guard')
        old = Journal({'1': {'status': 'POSTED', 'post_id': 'post-1'}})
        with self.assertRaises(BundleError): api.check_predecessors(['a'*64], lambda key: old)
        old.state['reconciliation'] = {'status': 'DELETED', 'evidence_url': 'https://bundle.social/dashboard/general/posts', 'checked_at': '2020-01-01T00:00:00+00:00'}
        api.check_predecessors(['a'*64], lambda key: old)

    def test_arabic_story_numbers_survive_text_rendering(self):
        import news_bot
        self.assertEqual(news_bot.sanitize('١ من ٣'), '١ من ٣')
        self.assertEqual(news_bot.sanitize('M5 — 512GB'), 'M5 - 512GB')


if __name__ == '__main__': unittest.main()
