import json
import unittest
from publishing_v2.autopilot.evidence import hydrate_timing, passages

SOURCE = {'id': 'article', 'text': 'Ceer revealed the new car on 21 September 2026. The official launch took place at the manufacturing complex.', 'source_type': 'news_article'}
DECISION = {'eligible': True, 'event_date': '2026-09-21', 'event_passage_id': 'article:p0', 'timing_basis': 'event', 'reason': 'Dated launch'}

class TimingPassageTests(unittest.TestCase):
    def test_program_copies_original_quote_without_model_transcription(self):
        result = hydrate_timing(DECISION, passages([SOURCE]))
        self.assertEqual(result['event_quote'], SOURCE['text'])
        self.assertEqual(result['event_source_id'], 'article')

    def test_ineligible_decision_may_omit_null_evidence_fields(self):
        decision = {
            'eligible': False,
            'timing_basis': 'report',
            'reason': 'No substantive current development',
        }
        result = hydrate_timing(decision, passages([SOURCE]))
        self.assertEqual(result['eligible'], False)
        self.assertIsNone(result.get('event_date'))
        self.assertNotIn('event_quote', result)
        self.assertNotIn('event_source_id', result)

    def test_eligible_decision_still_requires_date_and_passage(self):
        decision = {'eligible': True, 'timing_basis': 'event', 'reason': 'Current'}
        with self.assertRaises(ValueError):
            hydrate_timing(decision, passages([SOURCE]))

    def test_unknown_passage_and_model_authored_quote_are_rejected(self):
        for changes in ({'event_passage_id': 'invented'}, {'event_quote': 'Ceer ... launch'}):
            decision = dict(DECISION, **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                hydrate_timing(decision, passages([SOURCE]))
