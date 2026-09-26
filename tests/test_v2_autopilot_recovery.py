import unittest
from unittest.mock import patch
from urllib.request import Request

from publishing_v2.autopilot.agents import Agents
from publishing_v2.autopilot import sources
from publishing_v2.autopilot.runtime import Renderer
from daily_budget import BudgetBlocked
import test_v2_autopilot as fixtures


class Ledger:
    def __init__(self): self.reserved = []; self.settled = []
    def reserve(self, maximum, role):
        self.reserved.append((maximum, role)); return str(len(self.reserved))
    def settle(self, token, cost): self.settled.append((token, cost))


class FormatRecoveryTests(unittest.TestCase):
    def agent(self, answers):
        ledger = Ledger(); calls = []
        def transport(method, url, headers, payload):
            calls.append(payload)
            return {'status_code': 200, 'body': {'id': str(len(calls)),
                'stop_reason': 'end_turn', 'usage': {'input_tokens': 10, 'output_tokens': 10},
                'content': [{'type': 'text', 'text': answers[min(len(calls)-1, len(answers)-1)]}]}}
        return Agents(env={'ANTHROPIC_API_KEY': 'test'}, ledger=ledger, transport=transport), ledger, calls

    def test_malformed_completed_answer_gets_one_budgeted_fresh_attempt(self):
        agent, ledger, calls = self.agent(['{"candidates": [}', '{"candidates": []}'])
        self.assertEqual(agent.run('editor', {'candidates': []}), {'candidates': []})
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(ledger.reserved), 2)
        self.assertEqual(len(ledger.settled), 2)
        self.assertEqual(len(agent.receipts), 2)
        self.assertIn('format_error', agent.receipts[0])

    def test_repeated_bad_json_stops_after_two_calls(self):
        agent, ledger, calls = self.agent(['{broken'])
        with self.assertRaises(ValueError): agent.run('editor', {})
        self.assertEqual(len(calls), 2)

    def test_second_attempt_cannot_bypass_budget(self):
        agent, ledger, calls = self.agent(['{broken'])
        original = ledger.reserve
        def reserve(maximum, role):
            if ledger.reserved: raise BudgetBlocked('exhausted')
            return original(maximum, role)
        ledger.reserve = reserve
        with self.assertRaises(BudgetBlocked): agent.run('editor', {})
        self.assertEqual(len(calls), 1)

    def test_valid_rejection_does_not_get_resampled(self):
        agent, ledger, calls = self.agent(['{"checks":{"factual":false}}'])
        self.assertFalse(agent.run('reviewer', {})['checks']['factual'])
        self.assertEqual(len(calls), 1)


class RedirectRecoveryTests(unittest.TestCase):
    def handler(self):
        self.assertTrue(hasattr(sources, 'SourceRedirect'), 'validated redirect handler missing')
        return sources.SourceRedirect()

    def test_allowed_article_redirect_is_followed(self):
        req = Request('https://aawsat.com/node/5320224')
        result = self.handler().redirect_request(req, None, 301, 'moved', {},
                                               'https://aawsat.com/sport/5320224-story')
        self.assertEqual(result.full_url, 'https://aawsat.com/sport/5320224-story')

    def test_redirects_cannot_escape_allowlist_or_loop(self):
        req = Request('https://aawsat.com/node/5320224')
        for target in ['https://127.0.0.1/a', 'http://aawsat.com/a', 'https://evil.com/a',
                       'https://user:pass@aawsat.com/a']:
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.handler().redirect_request(req, None, 302, 'moved', {}, target)
        handler = self.handler()
        for i in range(3):
            handler.redirect_request(req, None, 302, 'moved', {}, f'https://aawsat.com/{i}')
        with self.assertRaises(ValueError):
            handler.redirect_request(req, None, 302, 'moved', {}, 'https://aawsat.com/4')


class VisualPlanningTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    render = fixtures.PipelineTests.render
    publish = fixtures.PipelineTests.publish
    pipeline = fixtures.PipelineTests.pipeline

    def test_unillustratable_candidate_is_held_after_text_before_render(self):
        pipeline = self.pipeline()
        def render(package, output): return self.render(package, output)
        render.plan_visuals = lambda candidate: []
        pipeline.render = render
        result = pipeline.run('local', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertIn('text_review', self.agent.calls)
        self.assertLess(self.agent.calls.index('writer'),self.agent.calls.index('text_review'))

    def test_writer_finishes_text_before_visual_options(self):
        pipeline = self.pipeline(); options = [{'asset_id': str(i)} for i in range(3)]
        def render(package, output): return self.render(package, output)
        render.plan_visuals = lambda candidate: options
        pipeline.render = render
        original = self.agent.run
        seen = []
        def run(role, data, images=()):
            if role == 'writer': seen.append(data.get('visual_options'))
            return original(role, data, images)
        self.agent.run = run
        self.assertEqual(pipeline.run('local', 'shadow')['status'], 'shadow_passed')
        self.assertEqual(seen, [[]])

    def test_renderer_plans_without_paid_visual_call(self):
        class Source:
            def images(self, query):
                return [{'asset_id': str(i), 'license': 'CC0', 'title': 'Jeddah',
                         'width': 1600, 'height': 1200} for i in range(3)]
        renderer = Renderer(object(), Source())
        self.assertTrue(hasattr(renderer, 'plan_visuals'))
        self.assertEqual(len(renderer.plan_visuals({'id': 'a',
            'editorial': {'research_query': 'Jeddah'}})), 3)
