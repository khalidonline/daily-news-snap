import copy
import json
import unittest
import test_v2_autopilot_recovery as helpers
import test_v2_autopilot as fixtures

class PayloadTests(unittest.TestCase):
    def test_review_omits_discovery_catalog_but_keeps_selected_evidence(self):
        data={'candidate':{'id':'ceer','visual_discovery':[{'description':'x'*100000}]},
              'cards':[{'image':{'asset_id':'selected','license':'All rights reserved'}}],
              'original_sources':[{'id':'article','text':'original source'}]}
        before=copy.deepcopy(data)
        agent,_,calls=helpers.FormatRecoveryTests().agent(['{}'])
        agent.run('reviewer',data)
        sent=json.loads(calls[0]['messages'][0]['content'][-1]['text'])
        self.assertNotIn('visual_discovery',sent['candidate'])
        self.assertEqual(sent['cards'],data['cards'])
        self.assertEqual(sent['original_sources'],data['original_sources'])
        self.assertEqual(data,before)

    def test_writer_does_not_receive_unverified_editor_proposals_as_facts(self):
        data={'candidate':{'id':'ceer','title':'source headline',
                           'editorial':{'why_saudi':'wrong city','angle':'invented claim'}},
              'research':{'claims':[{'fact':'verified city'}]}}
        agent,_,calls=helpers.FormatRecoveryTests().agent(['{}'])
        agent.run('writer',data)
        sent=json.loads(calls[0]['messages'][0]['content'][-1]['text'])
        self.assertNotIn('editorial',sent['candidate'])
        self.assertEqual(sent['research'],data['research'])

class StructuralFailureTests(unittest.TestCase):
    def test_oversized_input_does_not_pay_for_rewriting_same_candidate(self):
        fixture=fixtures.PipelineTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original=fixture.agent.run
        def run(role,data,images=()):
            if role=='reviewer':
                raise ValueError('agent_input_too_large')
            return original(role,data,images)
        fixture.agent.run=run
        result=fixture.pipeline().run('daily','shadow')
        self.assertEqual(result['status'],'held')
        self.assertEqual(fixture.agent.calls.count('writer'),2) # one per candidate
