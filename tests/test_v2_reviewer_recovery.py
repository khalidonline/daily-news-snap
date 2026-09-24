import hashlib
import unittest
from unittest.mock import patch

import recover_held_reviewer as recovery


class ReviewerRecoveryTests(unittest.TestCase):
    def test_reviewer_output_cap_is_bounded(self):
        self.assertEqual(recovery.REVIEWER_MAX_TOKENS, 4096)

    def test_changed_source_uses_saved_evidence_snapshot(self):
        saved = 'original saved excerpt'
        row = {'id':'s1','url':'https://example.com','text':saved,
               'retrieved_text_sha256':hashlib.sha256(b'full original source').hexdigest()}
        with patch.object(recovery, 'restore_text', return_value='publisher changed page'):
            restored = recovery.restore_sources([row])
        self.assertEqual(restored[0]['text'], saved)
        self.assertEqual(restored[0]['recovery_source_mode'], 'saved_evidence_snapshot')

    def test_exact_refetch_is_preferred(self):
        body = 'full original source'
        row = {'id':'s1','url':'https://example.com','text':'saved excerpt',
               'retrieved_text_sha256':hashlib.sha256(body.encode()).hexdigest()}
        with patch.object(recovery, 'restore_text', return_value=body):
            restored = recovery.restore_sources([row])
        self.assertEqual(restored[0]['text'], body)
        self.assertEqual(restored[0]['recovery_source_mode'], 'refetched_exact')


if __name__ == '__main__':
    unittest.main()
