import unittest
from unittest.mock import Mock

from publishing_v2.bundle_api import BundleClient, BundleError


class InterruptedReceiptTests(unittest.TestCase):
    def receipt(self, message, expected, *, placement='STORY', **overrides):
        row = dict(id='p', teamId='t', status='ERROR', data={'SNAPCHAT': {'type': placement}},
                   errorsVerbose={'SNAPCHAT': {'code': 'PUBLISH:INTERRUPTED', 'message': message}})
        row.update(overrides)
        client = Mock(team='t')
        client.call.return_value = row
        with self.assertRaises(BundleError) as failure:
            BundleClient.wait(client, 'p')
        self.assertIn(expected, str(failure.exception))
        self.assertNotIn('sensitive', str(failure.exception))
        client.call.assert_called_once_with('/post/p')

    def test_upload(self):
        self.receipt('Publishing was interrupted while the media was uploading. Nothing was published, so it is safe to retry.',
                     'الستوري: بحسب Bundle، ما اننشر')

    def test_confirmation(self):
        self.receipt('Publishing was interrupted before the platform confirmed this post. It may already be live, so check the account before retrying.',
                     'الأضواء: ممكن يكون اننشر', placement='SPOTLIGHT')

    def test_unknown_message_or_destination(self):
        self.receipt('sensitive', 'سناب: ممكن يكون اننشر', placement=None)

    def test_identity_first(self):
        self.receipt('sensitive', 'Receipt identity mismatch', teamId='wrong')

    def test_unrelated_error(self):
        self.receipt('sensitive', 'Post not confirmed', errorsVerbose={'SNAPCHAT': {'code': 'OTHER'}})
