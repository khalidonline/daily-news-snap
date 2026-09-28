import unittest
from publishing_v2.autopilot import agents


class OwnerMemoryTests(unittest.TestCase):
    def test_writer_and_both_reviews_receive_current_shared_rules(self):
        class Ledger:
            context = {}
            def reserve(self, amount, bot): return 'offline'
            def settle(self, token, amount): pass
        payloads = []
        def transport(method, url, headers, payload):
            payloads.append(payload)
            return {'status_code': 200, 'body': {'id': 'offline', 'stop_reason': 'end_turn',
                'usage': {'input_tokens': 10, 'output_tokens': 10},
                'content': [{'type': 'text', 'text': '{}'}]}}
        agent = agents.Agents(env={'ANTHROPIC_API_KEY': 'offline', 'PACKAGE_ID': 'test'},
                              ledger=Ledger(), transport=transport)
        for role in ('writer', 'text_review', 'reviewer'):
            agent.run(role, {})
            prompt = payloads[-1]['system']
            for rule in ('trigger-public-optional', 'single-paid-candidate', 'quiet-optional-ending',
                         'place-time-story', 'clear-info-useful-ending', 'approved-copy-visual-continuity',
                         'info-not-story-summary', 'photo-text-balance',
                         'ordinary-reader-payoff', 'specific-outcome-current-photo'):
                self.assertIn('[' + rule + ']', prompt)
            self.assertNotIn('If the angle itself remains weak, replace the candidate', prompt)
            self.assertTrue(agent.receipts[-1].get('owner_memory_version'))

    def test_source_and_scope_are_recorded_and_archive_does_not_enter_active_rules(self):
        from publishing_v2.autopilot import feedback
        self.assertTrue(hasattr(feedback, 'MEMORY_RECORDS'), 'structured owner memory missing')
        records = feedback.MEMORY_RECORDS
        self.assertEqual(len({r['id'] for r in records}), len(records))
        for record in records:
            self.assertTrue(record['source'])
            self.assertIn(record['scope'], ('general', 'package'))
            self.assertIn(record['status'], ('active', 'superseded'))
        archived = [r for r in records if r['status'] == 'superseded']
        self.assertTrue(archived)
        self.assertTrue(all(r['replaced_by'] for r in archived))
        self.assertNotIn('replace the candidate', str(feedback.EDITORIAL_FEEDBACK))
