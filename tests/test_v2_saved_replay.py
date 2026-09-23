import copy
import hashlib
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from test_v2_autopilot import NOW, research, draft, evidence
from publishing_v2.autopilot import policy
from publishing_v2.autopilot.replay import replay

class SavedReplayTests(unittest.TestCase):
    def setUp(self):
        sources=evidence()
        self.saved={'lane':'daily','expires_at':policy.expiry(NOW),
          'candidate':{'url':sources[0]['url'],'published_at':NOW.isoformat()},
          'timing':{'eligible':True,'event_date':'2026-09-17','event_source_id':'s1',
                    'event_quote':'17 September 2026','timing_basis':'event','reason':'Current event'},
          'sources':[dict(sources[0],retrieved_text_sha256=hashlib.sha256(sources[0]['text'].encode()).hexdigest())],
          'research':research(),'package':draft()}
        for c in self.saved['package']['cards']:c['image']={'asset_id':'saved-photo','sha256':'saved-hash'}
        self.calls=[];self.renders=0;self.saved_events=[]
        case=self
        class Agent:
            receipts=[]
            def run(self,role,data,images=()):
                case.calls.append(role)
                if role=='writer':return draft()
                if role=='reviewer':return {'checks':{k:True for k in policy.REVIEW_CHECKS},'card_checks':[{'readable':True,'relevant':True} for p in images],'reason':'Reviewed'}
                raise AssertionError(role)
        self.agent=Agent()
    def run_replay(self):
        with tempfile.TemporaryDirectory() as out:
            def render(package,folder):
                self.renders+=1
                self.assertTrue(all(c['image']['asset_id']=='saved-photo' for c in package['cards']))
                p=Path(folder)/'card.jpg';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'rendered')
                return [p]*len(package['cards'])
            return replay(self.saved,agent=self.agent,render=render,output=out,now=lambda:NOW,
                          restore=lambda row:row['text'],save=lambda state:self.saved_events.append(copy.deepcopy(state)))
    def test_only_writer_and_reviewer_and_no_readiness_approval(self):
        result=self.run_replay()
        self.assertEqual(self.calls,['writer','reviewer'])
        self.assertEqual(result['status'],'replay_review_passed')
        self.assertFalse(result['automated_readiness'])
        self.assertNotIn('receipt',result)
        self.assertNotIn('approval',result)
        self.assertEqual(self.saved_events[0]['status'],'working')
    def test_expired_source_stops_before_paid_calls(self):
        self.saved['expires_at']=(NOW-timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ValueError,'expired'):self.run_replay()
        self.assertEqual(self.calls,[])
    def test_changed_evidence_stops_before_paid_calls(self):
        self.saved['sources'][0]['retrieved_text_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'source_changed'):self.run_replay()
        self.assertEqual(self.calls,[])
    def test_writer_cannot_add_cards_with_unsaved_photos(self):
        original=self.agent.run
        def run(role,data,images=()):
            result=original(role,data,images)
            if role=='writer':result['cards'].append(copy.deepcopy(result['cards'][-1]))
            return result
        self.agent.run=run
        with self.assertRaisesRegex(ValueError,'card_count'):self.run_replay()
        self.assertEqual(self.calls,['writer']);self.assertEqual(self.renders,0)

    def test_rejected_review_is_saved_and_never_passes(self):
        original=self.agent.run
        def run(role,data,images=()):
            result=original(role,data,images)
            if role=='reviewer':result['checks']['story_coherent']=False
            return result
        self.agent.run=run
        with self.assertRaisesRegex(ValueError,'editorial_review_rejected'):self.run_replay()
        self.assertEqual(self.saved_events[-1]['status'],'held')
        self.assertFalse(self.saved_events[-1]['review']['checks']['story_coherent'])
