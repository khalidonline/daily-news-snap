import copy, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone
from publishing_v2.bundle_api import BundleClient, BundleError, publish

class Journal:
    def __init__(self): self.state = {}
    def read(self): return copy.deepcopy(self.state)
    def save(self, value): self.state = copy.deepcopy(value)

class Client:
    def __init__(self, remaining): self.remaining=remaining; self.uploads=[]; self.checked=[]
    def ensure_capacity(self, count):
        self.checked.append(count)
        if count > self.remaining: raise BundleError('daily_quota_insufficient')
    def upload(self, item): self.uploads.append(item); return 'upload'
    def create(self, title, upload): return 'post'
    def wait(self, post_id): pass

class QuotaTests(unittest.TestCase):
    def test_whole_package_held_before_first_upload(self):
        c=Client(3)
        with self.assertRaises(BundleError): publish(c,Journal(),'four',[1,2,3,4])
        self.assertEqual(c.uploads,[])
    def test_partial_counts_only_new_posts(self):
        c,j=Client(1),Journal(); j.state={'1':{'status':'POSTED','post_id':'old'}}
        publish(c,j,'two',[1,2]); self.assertEqual(c.checked,[1])
        self.assertEqual(c.uploads,[2])
    def test_uncertain_anywhere_blocks_entire_batch(self):
        c,j=Client(9),Journal(); j.state={'2':{'status':'SENDING','upload_id':'u'}}
        with self.assertRaises(BundleError): publish(c,j,'two',[1,2])
        self.assertEqual(c.uploads,[])
    def test_quota_response_date_and_account_must_match(self):
        with patch.dict('os.environ',{'BUNDLE_API_KEY':'x','BUNDLE_TEAM_ID':'team'}):
            c=BundleClient()
        account={'id':'account','username':'executivesaudi','teamId':'team','type':'SNAPCHAT'}
        quota={'socialAccountId':'account','type':'SNAPCHAT','date':'2026-09-25T00:00:00Z','posts':{'used':20,'limit':20,'remaining':0}}
        self.assertTrue(hasattr(c,'ensure_capacity'))
        with patch.object(c,'call',side_effect=[account,quota]):
            with self.assertRaises(BundleError): c.ensure_capacity(1,now=datetime(2026,9,25,tzinfo=timezone.utc))
        quota['posts']={'used':0,'limit':20,'remaining':20}
        with patch.object(c,'call',side_effect=[account,quota]):
            with self.assertRaises(BundleError): c.ensure_capacity(1,now=datetime(2026,9,26,tzinfo=timezone.utc))

class DeliveryTests(unittest.TestCase):
    def test_paid_reservation_keeps_package_and_stage(self):
        from daily_budget import Ledger
        from test_daily_budget import MemoryStore
        s=MemoryStore(); ledger=Ledger(s)
        ledger.context={'package_id':'apple','stage':'image_check','request_attempt':2}
        day,ident=ledger.reserve(100,'autopilot:image_check')
        row=s.read(day)[1]['entries'][ident]
        self.assertEqual(row.get('package_id'),'apple')
        self.assertEqual(row.get('request_attempt'),2)

    def test_missing_saved_media_never_calls_renderer(self):
        from publishing_v2.autopilot.pipeline import Pipeline
        rendered=[]; j=Journal()
        p=Pipeline(agent=None,sources=None,render=lambda *args:rendered.append(args),store=j,
            publish=None,output='unused',now=lambda:datetime.now(timezone.utc))
        state={'package':{},'paths':['/nonexistent/frozen-card.jpg']}
        result=p.deliver(state)
        self.assertEqual(rendered,[])
        self.assertEqual(result['status'],'delivery_pending')

if __name__=='__main__': unittest.main()
