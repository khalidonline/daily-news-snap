import json
import unittest
import test_v2_autopilot_recovery as helpers

SOURCE = {'id': 'article', 'text': 'Ceer revealed the new car on 21 September 2026. The official launch took place at the manufacturing complex.', 'source_type': 'news_article'}
DECISION = {'eligible': True, 'event_date': '2026-09-21', 'event_passage_id': 'article:p0', 'timing_basis': 'event', 'reason': 'Dated launch'}

class TimingPassageTests(unittest.TestCase):
    def test_program_copies_original_quote_without_model_transcription(self):
        agent, _, calls = helpers.FormatRecoveryTests().agent([json.dumps(DECISION)])
        result = agent.run('timing', {'sources': [SOURCE]})
        self.assertEqual(result['event_quote'], SOURCE['text'])
        self.assertEqual(result['event_source_id'], 'article')
        payload = json.loads(calls[0]['messages'][0]['content'][-1]['text'])
        self.assertNotIn('text', payload['sources'][0])
        self.assertEqual(payload['passages'][0]['quote'], SOURCE['text'])

    def test_unknown_passage_and_model_authored_quote_are_rejected(self):
        for changes in ({'event_passage_id': 'invented'}, {'event_quote': 'Ceer ... launch'}):
            agent, _, _ = helpers.FormatRecoveryTests().agent([json.dumps(dict(DECISION, **changes))])
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                agent.run('timing', {'sources': [SOURCE]})
