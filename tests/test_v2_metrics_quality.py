import unittest
from datetime import datetime,timezone
try:
 from publishing_v2.metrics_quality import assess
except ImportError:
 assess=None
class QualityTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,1,12,tzinfo=timezone.utc)
  self.row={'views':0,'viewsUnique':0,'createdAt':'2026-10-01T07:00:00Z','updatedAt':'2026-10-01T07:00:00Z'}
 def call(self,rows,**kw):
  self.assertIsNotNone(assess,'metrics quality layer must exist')
  return assess(rows,self.now,placement=kw.pop('placement','STORY'),**kw)
 def test_creation_zero_is_unverified(self):
  r=self.call([self.row]);self.assertEqual(r['status'],'unverified_zero');self.assertFalse(r['usable']);self.assertEqual(r['values']['views'],0)
 def test_newer_provider_update_validates_zero(self):
  self.row['updatedAt']='2026-10-01T11:00:00Z';self.assertTrue(self.call([self.row])['usable'])
 def test_sort_not_api_order(self):
  newer=dict(self.row,views=50,updatedAt='2026-10-01T11:00:00Z')
  for rows in [[newer,self.row],[self.row,newer]]:self.assertEqual(self.call(rows)['values']['views'],50)
 def test_missing_not_zero(self):self.assertIsNone(self.call([self.row])['values']['shares'])
 def test_empty_unavailable(self):self.assertEqual(self.call([])['status'],'unavailable')
 def test_stale_nonzero_not_usable(self):
  old=dict(self.row,views=50,createdAt='2026-09-20T01:00:00Z',updatedAt='2026-09-20T02:00:00Z')
  self.assertFalse(self.call([old])['usable'])
 def test_future_timestamp_rejected(self):
  self.row['updatedAt']='2027-10-01T11:00:00Z';self.assertEqual(self.call([self.row])['status'],'invalid_timestamp')
 def test_separate_placements(self):self.assertEqual(self.call([self.row],placement='SAVED_STORY')['placement'],'SAVED_STORY')
 def test_invalid_values_not_coerced(self):
  self.row.update(views=-1);self.assertEqual(self.call([self.row])['status'],'invalid_value')
 def test_missing_time_not_assumed_fresh(self):
  self.row.pop('updatedAt');self.assertFalse(self.call([self.row])['usable'])

class CollectorTests(unittest.TestCase):
 def test_preserves_post_placement_and_uses_get_only(self):
  from publishing_v2.metrics_quality import collect
  class Client:
   team='team'
   def call(self,path):
    if not path.startswith('/analytics/post?'):raise AssertionError('unexpected endpoint')
    return {'post':{'id':'p','teamId':'team','status':'POSTED','data':{'SNAPCHAT':{'type':'SAVED_STORY'}}},'items':[]}
  r=collect(Client(),[{'package':'a','post_id':'p','placement':'SAVED_STORY'}],datetime.now(timezone.utc))
  self.assertEqual(r['reports'][0]['status'],'unavailable');self.assertEqual(r['reports'][0]['placement'],'SAVED_STORY')
 def test_wrong_account_rejected(self):
  from publishing_v2.metrics_quality import collect
  class Client:
   team='team'
   def call(self,path):return {'post':{'id':'p','teamId':'other','status':'POSTED','data':{'SNAPCHAT':{'type':'STORY'}}},'items':[]}
  with self.assertRaises(ValueError):collect(Client(),[{'package':'a','post_id':'p','placement':'STORY'}],datetime.now(timezone.utc))
