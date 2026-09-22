import unittest
from unittest.mock import patch
from publishing_v2.autopilot import report


class UserReportTests(unittest.TestCase):
    def test_manual_review_is_silent_even_when_it_passes_or_fails(self):
        for status in ['shadow_passed', 'held']:
            self.assertIsNone(report.user_message({'mode':'shadow', 'results':[
                {'lane':'daily','status':status,'reason':'BudgetBlocked'}]}, {}))
        with patch.dict('os.environ', {}, clear=True), patch.object(report.Path, 'exists', return_value=False), \
                patch.object(report, 'request') as request, patch.object(report, 'GitHubJournal') as journal:
            self.assertEqual(report.main(), 0)
            request.assert_not_called()
            journal.assert_not_called()

    def test_scheduled_shadow_is_not_reported_as_publication(self):
        text = report.user_message({'mode':'shadow','results':[{'lane':'daily','status':'shadow_passed'}]},
                                  {'GITHUB_EVENT_NAME':'schedule'})
        self.assertIn('لم تُنشر', text)
        self.assertIn('مرحلة التحقق', text)
        self.assertNotIn('shadow', text)

    def test_only_confirmed_receipts_claim_success(self):
        row = {'lane':'daily','status':'published','title':'قصة مبابي',
               'receipt':{'status':'POSTED','post_ids':['1','2','3']}}
        text = report.user_message({'mode':'live','results':[row]}, {})
        self.assertIn('قصة مبابي — 3 بطاقات', text)
        row['receipt']['status'] = 'PENDING'
        self.assertNotIn('✅', report.user_message({'mode':'live','results':[row]}, {}))

    def test_unknown_and_partial_delivery_never_claim_active_repair(self):
        for rows in [[], [{'lane':'local','status':'delivery_pending'}]]:
            text = report.user_message({'mode':'live','results':rows}, {})
            self.assertIn('قبل إعادة المحاولة', text)
            self.assertNotIn('جار', text)
            self.assertNotIn('github', text)
