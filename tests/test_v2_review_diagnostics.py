import unittest
from publishing_v2.autopilot.policy import REVIEW_CHECKS, validate_review

class ReviewDiagnosticsTests(unittest.TestCase):
    def test_detailed_internal_report_does_not_reject_valid_cards(self):
        review = {'reason': 'Source-by-source verification. ' * 200,
                  'checks': dict.fromkeys(REVIEW_CHECKS, True),
                  'card_checks': [{'readable': True, 'relevant': True}] * 3}
        validate_review(review, 3)
        review['checks']['factual'] = False
        with self.assertRaisesRegex(ValueError, 'editorial_review_rejected'):
            validate_review(review, 3)

    def test_empty_report_and_failed_visual_still_rejected(self):
        review = {'reason': '', 'checks': dict.fromkeys(REVIEW_CHECKS, True),
                  'card_checks': [{'readable': True, 'relevant': False}]}
        with self.assertRaises(ValueError): validate_review(review, 1)
        review['reason'] = 'Detailed audit. ' * 200
        with self.assertRaisesRegex(ValueError, 'visual_review_rejected'):
            validate_review(review, 1)
