import unittest
from datetime import datetime,timezone,timedelta
from publishing_v2.autopilot.runtime import rollout_ready
class IndependentReadiness(unittest.TestCase):
    def test_daily_does_not_require_local(self):
        now=datetime(2026,9,26,tzinfo=timezone.utc)
        row={'status':'shadow_passed','engine':'approved','at':now.isoformat()}
        self.assertTrue(rollout_ready({'daily':row},'approved',now,lane='daily'))
        self.assertFalse(rollout_ready({'daily':row},'approved',now,lane='local'))
        self.assertFalse(rollout_ready({'daily':row},'different',now,lane='daily'))
        self.assertFalse(rollout_ready({'daily':dict(row,at=(now-timedelta(days=4)).isoformat())},'approved',now,lane='daily'))
        self.assertFalse(rollout_ready({'daily':dict(row,status='held')},'approved',now,lane='daily'))
