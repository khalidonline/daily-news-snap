import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone
from PIL import Image
from daily_budget import BudgetBlocked, Ledger
from publishing_v2.autopilot.agents import Agents, parse_object
from publishing_v2.autopilot.sources import safe_url, reusable_image, Sources


class Store:
    def __init__(self): self.row = None
    def read(self, day): return 'v1', copy.deepcopy(self.row)
    def write(self, day, version, row): self.row = copy.deepcopy(row); return True


class AgentTests(unittest.TestCase):
    def test_plain_newlines_inside_json_strings_are_normalized_safely(self):
        self.assertEqual(parse_object('{"reason":"first\nsecond"}'), {'reason': 'first\nsecond'})
        with self.assertRaises(ValueError): parse_object('{"reason":"bad\x00value"}')
        with self.assertRaises(ValueError): parse_object('{}\n{}')

    def test_complete_json_fence_is_normalized_but_mixed_prose_rejected(self):
        self.assertEqual(parse_object('```json\n{"candidates": []}\n```'), {'candidates': []})
        with self.assertRaises(ValueError): parse_object('Here is the answer: {"candidates": []}')

    def test_fenced_decision_with_plain_rationale_accepts_only_single_object(self):
        self.assertEqual(parse_object('```JSON\n{"image_ids": [null]}\n```\nNo suitable image found.'), {'image_ids': [None]})
        with self.assertRaises(ValueError): parse_object('```json\n{}\n```\n{"image_ids": ["different"]}')

    def setUp(self):
        self.store = Store()
        self.ledger = Ledger(self.store, now=lambda: datetime(2026, 9, 17, tzinfo=timezone.utc))

    def agent(self, transport):
        return Agents(env={'ANTHROPIC_API_KEY': 'credential-sentinel-never-in-prompts'}, ledger=self.ledger, transport=transport)

    def test_budget_is_reserved_before_request_and_settled(self):
        def transport(method, url, headers, payload):
            self.assertEqual(payload['output_config']['effort'], 'medium')
            self.assertGreaterEqual(payload['max_tokens'], 8000)
            self.assertGreater(sum(e['charged_micro_usd'] for e in self.store.row['entries'].values()), 0)
            self.assertNotIn('credential-sentinel-never-in-prompts', payload['system'])
            return {'status_code': 200, 'body': {'id': 'receipt', 'stop_reason': 'end_turn',
                    'usage': {'input_tokens': 100, 'output_tokens': 10},
                    'content': [{'type': 'text', 'text': '{"candidates": []}'}]}}
        result = self.agent(transport).run('editor', {'candidates': []})
        self.assertEqual(result, {'candidates': []})
        self.assertTrue(all(e['status'] == 'settled' for e in self.store.row['entries'].values()))

    def test_incomplete_response_is_accounted_and_diagnosable(self):
        def transport(method, url, headers, payload):
            self.assertGreaterEqual(payload['max_tokens'], 6000)
            return {'status_code': 200, 'body': {'id': 'truncated', 'stop_reason': 'max_tokens',
                'usage': {'input_tokens': 100, 'output_tokens': 2000},
                'content': [{'type': 'text', 'text': '{'}]}}
        agent = self.agent(transport)
        with self.assertRaises(RuntimeError): agent.run('editor', {'candidates': []})
        self.assertEqual(agent.receipts[0]['stop_reason'], 'max_tokens')
        self.assertTrue(all(e['status'] == 'settled' for e in self.store.row['entries'].values()))

    def test_production_agent_uses_bounded_long_review_timeout(self):
        reply = {'status_code': 200, 'body': {'id': 'r', 'stop_reason': 'end_turn',
                 'usage': {'input_tokens': 10, 'output_tokens': 10},
                 'content': [{'type': 'text', 'text': '{"candidates": []}'}]}}
        with patch('publishing_v2.providers._default_transport', return_value=reply) as transport:
            self.agent(None).run('editor', {'candidates': []})
        self.assertEqual(transport.call_args.kwargs['timeout_seconds'], 180)

    def test_ambiguous_provider_error_keeps_reservation(self):
        def transport(*args): raise TimeoutError()
        with self.assertRaises(RuntimeError): self.agent(transport).run('writer', {})
        self.assertTrue(all(e['status'] == 'reserved' for e in self.store.row['entries'].values()))

    def test_no_call_when_budget_exhausted(self):
        self.ledger.reserve(3_000_000, 'another-package')
        def forbidden(*args): self.fail('Paid request escaped the budget')
        with self.assertRaises(BudgetBlocked): self.agent(forbidden).run('editor', {})

    def test_unknown_role_cannot_receive_publishing_tools(self):
        with self.assertRaises(ValueError): self.agent(None).run('publisher', {})

    def test_reviewer_gets_images_in_a_fresh_request(self):
        def transport(method, url, headers, payload):
            self.assertEqual(payload['output_config']['effort'], 'high')
            self.assertEqual(payload['max_tokens'], 8192)
            self.assertEqual(len(payload['messages']), 1)
            self.assertEqual(payload['messages'][0]['content'][0]['type'], 'image')
            self.assertNotIn('tools', payload)
            return {'status_code': 200, 'body': {'id': 'r', 'stop_reason': 'end_turn',
                'usage': {'input_tokens': 500, 'output_tokens': 10},
                'content': [{'type': 'text', 'text': '{}'}]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'image.jpg'; Image.new('RGB', (1080, 1920)).save(path)
            self.agent(transport).run('reviewer', {}, images=[path])


class SourceTests(unittest.TestCase):
    def test_image_recovery_searches_cc0_and_caches_success(self):
        good = {'asset_id': 'one', 'license': 'CC0'}
        with patch('publishing_v2.autopilot.sources.search_commons', side_effect=[
                [{'license': 'CC BY-SA 4.0'}], [good]]):
            source = Sources()
            self.assertEqual(source.images('date palm'), [good])
            self.assertEqual(source.images('date palm'), [good])

    def test_retrieval_rejects_credentials_private_and_unlisted_hosts(self):
        for url in ['http://www.bbc.com/news/a', 'https://127.0.0.1/a',
                    'https://www.bbc.com@evil.com/a', 'https://www.bbc.com:8443/a',
                    'https://www.bbc.com.evil.com/a']:
            with self.subTest(url=url), self.assertRaises(ValueError): safe_url(url)

    def test_encoded_feed_markup_does_not_reach_editor_as_links(self):
        from publishing_v2.autopilot.sources import plain
        self.assertEqual(plain('News &lt;a href="https://example.com"&gt;subject&lt;/a&gt;'), 'News subject')

    def test_model_cannot_self_authorize_image_rights(self):
        self.assertFalse(reusable_image({'license': 'CC BY-SA 4.0', 'licensing_verified': True}))
        self.assertFalse(reusable_image({'license': 'Public domain', 'restrictions': 'trademark restrictions'}))
        self.assertTrue(reusable_image({'license': 'CC0', 'restrictions': '', 'attribution_required': 'false'}))


if __name__ == '__main__': unittest.main()
