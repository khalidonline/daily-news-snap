import unittest
from datetime import datetime, timezone
from publishing_v2.autopilot.runtime import Renderer
import daily_budget

class CostRecoveryTests(unittest.TestCase):
    def test_recovery_keeps_card_subject_when_event_subject_has_photos(self):
        class Sources:
            recovery = True
            def subject_images(self, query, subject):
                return [{'asset_id': query, 'license': 'CC0', 'title': query}]
        renderer = Renderer(None, Sources())
        rows = renderer.image_options({'image_query': 'Saudi flag'},
            {'candidate': {'resolved_subjects': [{'name': 'Saudi National Day'}]}})
        self.assertIn('Saudi flag', [r['asset_id'] for r in rows])
        self.assertEqual(rows[0]['asset_id'], 'Saudi National Day')

    def test_trial_allowance_expires_at_saudi_midnight(self):
        limit = daily_budget.autopilot_daily_limit
        self.assertEqual(limit(datetime(2026,9,23,20,59,tzinfo=timezone.utc)), 8000000)
        self.assertEqual(limit(datetime(2026,9,23,21,0,tzinfo=timezone.utc)), 3000000)
        self.assertEqual(limit(datetime(2026,10,1,tzinfo=timezone.utc), 8000000), 3000000)
        self.assertEqual(limit(datetime(2026,9,23,tzinfo=timezone.utc), 3000000), 3000000)
