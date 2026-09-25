import copy
import unittest
from unittest.mock import patch
import io
from publishing_v2.bundle_api import publish, BundleError, verify_account, BundleClient

class Journal:
    def __init__(self): self.state = {}; self.fail = False
    def read(self): return copy.deepcopy(self.state)
    def save(self, state):
        if self.fail: raise BundleError('journal failed')
        self.state = copy.deepcopy(state)

class Client:
    def ensure_capacity(self, count): pass
    def __init__(self): self.sent=[]; self.status='POSTED'; self.fail=False
    def upload(self, media): return 'upload'
    def create(self, title, upload):
        self.sent.append(title)
        if self.fail: raise BundleError('timeout')
        return 'post-' + str(len(self.sent))
    def wait(self, post_id):
        if self.status != 'POSTED': raise BundleError('pending')

class PublishingTests(unittest.TestCase):
    def test_bundle_identifies_its_api_client(self):
        with patch.dict('os.environ', {'BUNDLE_API_KEY':'test-key','BUNDLE_TEAM_ID':'team'}):
            with patch('urllib.request.urlopen', return_value=io.BytesIO(b'{}')) as opened:
                BundleClient().call('/health')
                self.assertEqual(opened.call_args.args[0].get_header('User-agent'),
                                 'ExecutiveSaudiPublisher/1.0')

    def test_resuming_completed_package_does_not_send_again(self):
        c,j=Client(),Journal()
        publish(c,j,'story',['one','two'])
        publish(c,j,'story',['one','two'])
        self.assertEqual(len(c.sent),2)
    def test_ambiguous_create_blocks_retry(self):
        c,j=Client(),Journal(); c.fail=True
        with self.assertRaises(BundleError): publish(c,j,'story',['one'])
        c.fail=False
        with self.assertRaises(BundleError): publish(c,j,'story',['one'])
        self.assertEqual(len(c.sent),1)
    def test_journal_failure_prevents_create(self):
        c,j=Client(),Journal(); j.fail=True
        with self.assertRaises(BundleError): publish(c,j,'story',['one'])
        self.assertEqual(c.sent,[])
    def test_pending_receipt_resumes_without_resending(self):
        c,j=Client(),Journal(); c.status='SCHEDULED'
        with self.assertRaises(BundleError): publish(c,j,'story',['one','two'])
        self.assertEqual(len(c.sent),1)
        c.status='POSTED'; publish(c,j,'story',['one','two'])
        self.assertEqual(len(c.sent),2)
    def test_wrong_or_disconnected_account_rejected(self):
        good={'username':'executivesaudi','teamId':'team','type':'SNAPCHAT','id':'x'}
        verify_account(good,'team')
        for change in [{'username':'other'},{'deletedAt':'today'},{'deleteOn':'tomorrow'},{'type':'TIKTOK'},{'teamId':'other'}]:
            with self.assertRaises(BundleError): verify_account(good | change,'team')

if __name__ == '__main__': unittest.main()
