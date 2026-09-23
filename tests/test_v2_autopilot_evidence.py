import unittest
from publishing_v2.autopilot.evidence import passages, hydrate, hydrate_timing


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

    def test_timing_extra_fields_are_ignored_but_evidence_is_source_bound(self):
        data = {'eligible': True, 'event_date': '2026-09-18',
                'event_passage_id': self.rows[0]['id'], 'timing_basis': 'event',
                'reason': 'Current event', 'confidence': 0.99,
                'event_source_id': 'invented', 'event_quote': 'invented'}
        result = hydrate_timing(data, self.rows)
        self.assertNotIn('confidence', result)
        self.assertEqual(result['event_source_id'], self.rows[0]['source_id'])
        self.assertEqual(result['event_quote'], self.rows[0]['quote'])
        self.assertNotEqual(result['event_quote'], 'invented')

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

    def test_wrong_id_types_are_rejected_without_crashing_coordinator(self):
        for ident in [[], {}, None, 12]:
            with self.subTest(ident=ident), self.assertRaises(ValueError):
                hydrate({'event_date': None, 'event_passage_id': None, 'sensitive': False,
                         'claims': [{'id': 'c1', 'fact': 'Fact', 'passage_id': ident}]}, self.rows)

    def test_missing_daily_date_is_a_candidate_rejection(self):
        from datetime import datetime, timezone
        from publishing_v2.autopilot.policy import validate_research
        data = hydrate({'event_date': None, 'event_passage_id': None, 'sensitive': False,
                        'claims': [{'id': 'c1', 'fact': 'Fact', 'passage_id': self.rows[0]['id']}]}, self.rows)
        with self.assertRaisesRegex(ValueError, 'missing_event_date'):
            validate_research(data, self.sources, 'daily', datetime.now(timezone.utc))

    def test_current_report_does_not_assert_underlying_event_date(self):
        from datetime import datetime, timezone
        from publishing_v2.autopilot.policy import reporting_time, validate_research
        sources = [dict(self.sources[0], source_type='news_article')]
        research = hydrate({'event_date': None, 'event_passage_id': None, 'sensitive': False,
            'claims': [{'id': 'c1', 'fact': 'Fact', 'passage_id': self.rows[0]['id']}]}, self.rows)
        result = reporting_time(research, sources,
            {'url': 'https://example.com', 'published_at': '2026-09-18T01:00:00+00:00'}, 'daily')
        self.assertEqual(result['timing_basis'], 'report_date')
        validate_research(result, sources, 'daily', datetime(2026,9,18,tzinfo=timezone.utc))
        with self.assertRaisesRegex(ValueError, 'event_outside_window'):
            validate_research(result, sources, 'daily', datetime(2026,9,22,tzinfo=timezone.utc))
        self.assertIs(reporting_time(research, self.sources,
            {'published_at': '2026-09-18T01:00:00+00:00'}, 'daily'), research)
