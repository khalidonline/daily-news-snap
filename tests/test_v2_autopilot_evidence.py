import unittest
from publishing_v2.autopilot.evidence import passages, hydrate


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.sources = [{'id': 'article', 'url': 'https://example.com',
                         'text': 'Today the festival opened in Riyadh. ' + ' '.join('word'+str(i) for i in range(300))}]
        self.rows = passages(self.sources)

    def test_passages_are_exact_bounded_source_spans(self):
        self.assertGreater(len(self.rows), 10)
        for row in self.rows:
            self.assertIn(row['quote'], self.sources[0]['text'])
            self.assertLessEqual(len(row['quote'].split()), 22)

    def test_model_cannot_supply_or_change_citation_text(self):
        data = {'sensitive': False, 'event_date': '2026-09-18',
                'event_passage_id': self.rows[0]['id'],
                'claims': [{'id': 'c1', 'passage_id': self.rows[1]['id'], 'fact': 'Fact'}]}
        result = hydrate(data, self.rows)
        self.assertEqual(result['claims'][0]['quote'], self.rows[1]['quote'])
        data['claims'][0]['quote'] = 'invented'
        with self.assertRaises(ValueError): hydrate(data, self.rows)

    def test_unknown_passage_cannot_be_evidence(self):
        with self.assertRaises(ValueError):
            hydrate({'sensitive': False, 'event_date': None, 'event_passage_id': None,
                     'claims': [{'id': 'c1', 'fact': 'Fact', 'passage_id': 'unknown'}]}, self.rows)

    def test_eight_claims_and_event_fit_source_excerpt_cap(self):
        data = {'sensitive': False, 'event_date': '2026-09-18',
                'event_passage_id': self.rows[8]['id'], 'claims': [
                    {'id': str(i), 'fact': 'Fact', 'passage_id': row['id']}
                    for i, row in enumerate(self.rows[:8])]}
        from publishing_v2.autopilot.policy import evidence_snapshot
        result = hydrate(data, self.rows)
        self.assertLessEqual(len(evidence_snapshot(result, self.sources)[0]['text'].split()), 200)

    def test_paid_research_adapter_resolves_only_retrieved_passages(self):
        import json
        from publishing_v2.autopilot.agents import Agents
        class Ledger:
            def reserve(self, maximum, role): return 'token'
            def settle(self, token, cost): pass
        def transport(method, url, headers, payload):
            request = json.loads(payload['messages'][0]['content'][0]['text'])
            self.assertNotIn('text', request['sources'][0])
            chosen = request['passages'][0]['id']
            response = {'sensitive': False, 'event_date': None, 'event_passage_id': None,
                        'claims': [{'id': 'c1', 'fact': 'Fact', 'passage_id': chosen}]}
            return {'status_code': 200, 'body': {'id': 'r', 'stop_reason': 'end_turn',
                'usage': {'input_tokens': 100, 'output_tokens': 100},
                'content': [{'type': 'text', 'text': json.dumps(response)}]}}
        agent = Agents(env={'ANTHROPIC_API_KEY': 'test'}, ledger=Ledger(), transport=transport)
        result = agent.run('researcher', {'sources': self.sources})
        self.assertEqual(result['claims'][0]['quote'], self.rows[0]['quote'])
