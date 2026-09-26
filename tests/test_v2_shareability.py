# Owner 2026-09-26: packages must be worth forwarding, not just correct.
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from publishing_v2.autopilot import agents, policy
from publishing_v2.autopilot.pipeline import Pipeline
from test_v2_autopilot import NOW, FakeAgent, FakeSources, MemoryStore, draft, research


def option(n, claims=('c1',)):
    return {'title': f'عنوان يشد {n}', 'opening': f'معلومة مدهشة {n}',
            'share_line': f'تدري إن {n}؟', 'claim_ids': list(claims)}


class HookAgent(FakeAgent):
    def __init__(self, options=None, choice=2):
        super().__init__()
        self.options = options if options is not None else [option(0), option(1), option(2)]
        self.choice, self.inputs = choice, {}

    def run(self, role, data, images=()):
        self.inputs.setdefault(role, []).append(copy.deepcopy(data))
        if role == 'hooks':
            self.calls.append(role)
            return {'options': copy.deepcopy(self.options)}
        if role == 'hook_judge':
            self.calls.append(role)
            return {'choice': self.choice, 'reason': 'أقوى مفارقة'}
        return super().run(role, data, images)


class HookPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def render(self, package, output):
        output.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, _ in enumerate(package['cards']):
            path = output / f'{i}.jpg'
            path.write_bytes(f'pixels {i}'.encode())
            paths.append(path)
        return paths

    def run_pipeline(self, agent, hooks=True):
        pipeline = Pipeline(agent=agent, sources=FakeSources(), render=self.render, store=MemoryStore(),
                            publish=lambda p, paths: None, output=Path(self.temp.name),
                            now=lambda: NOW, hooks=hooks)
        return pipeline.run('daily', 'shadow')

    def test_judged_hook_reaches_writer_and_is_audited(self):
        agent = HookAgent(choice=2)
        result = self.run_pipeline(agent)
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertLess(agent.calls.index('hooks'), agent.calls.index('hook_judge'))
        self.assertLess(agent.calls.index('hook_judge'), agent.calls.index('writer'))
        self.assertEqual(agent.inputs['writer'][0]['chosen_hook'], option(2))
        # The judge sees the viewer-facing text only, never claims or research.
        self.assertEqual(set(agent.inputs['hook_judge'][0]['options'][0]), {'title', 'opening', 'share_line'})
        self.assertEqual(result['hook']['choice'], 2)
        self.assertIn('hook_chosen', [e['event'] for e in result['audit']])

    def test_unsupported_hook_is_dropped_but_package_continues(self):
        agent = HookAgent(options=[option(0), option(1, claims=('c9',)), option(2)])
        result = self.run_pipeline(agent)
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertNotIn('hook_judge', agent.calls)
        self.assertNotIn('chosen_hook', agent.inputs['writer'][0])
        skipped = [e for e in result['audit'] if e['event'] == 'hook_skipped']
        self.assertEqual(skipped[0]['reason'], 'unsupported_hook_claim')

    def test_invalid_judge_choice_is_dropped(self):
        agent = HookAgent(choice=3)
        result = self.run_pipeline(agent)
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertNotIn('chosen_hook', agent.inputs['writer'][0])

    def test_hooks_off_keeps_the_original_call_sequence(self):
        agent = HookAgent()
        self.run_pipeline(agent, hooks=False)
        self.assertNotIn('hooks', agent.calls)

    def test_hooks_never_see_editor_rationale(self):
        # The editor's angle is unverified; hooks get research-bound input only.
        # Stop at encoding, before any budget reservation or paid request.
        runner = agents.Agents(env={'ANTHROPIC_API_KEY': 'x'}, ledger=None)
        with patch.object(agents.json, 'dumps', side_effect=RuntimeError('stop')) as dumps:
            with self.assertRaises(RuntimeError):
                runner._run_once('hooks', {'candidate': {'id': 'a', 'editorial': {'angle': 'x'}},
                                           'research': research()})
        self.assertNotIn('editorial', dumps.call_args.args[0]['candidate'])


class ShareabilityPolicyTests(unittest.TestCase):
    def test_arrow_symbols_are_rejected_before_render(self):
        package = draft()
        package['cards'][1]['body'] = 'SLS للعوائل ← في جزيرة شورى'
        with self.assertRaisesRegex(ValueError, 'unsupported_arrow_symbol'):
            policy.validate_draft(package, research())

    def test_plain_side_note_passes(self):
        package = draft()
        package['cards'][1]['body'] = 'SLS للعوائل. في جزيرة شورى، وتوصلها بالسيارة.'
        policy.validate_draft(package, research())

    def test_prompts_carry_the_owner_standard_to_every_gate(self):
        for role in ('writer', 'card_repair', 'hooks'):
            self.assertIn('تدري إن', agents.PROMPTS[role])
            self.assertIn('NEVER use the «X: من ... إلى ...» pattern', agents.PROMPTS[role])
        for role in ('text_review', 'reviewer'):
            self.assertIn('«X: من ... إلى ...» pattern', agents.PROMPTS[role])
        self.assertIn('SURPRISE HUNT', agents.PROMPTS['researcher'])
        self.assertIn('share_reason is the most important field', agents.PROMPTS['editor'])
        self.assertIn('22-year-old Saudi', agents.PROMPTS['hook_judge'])

    def test_production_runtime_enables_hooks(self):
        source = Path(__file__).resolve().parents[1].joinpath('publishing_v2/autopilot/runtime.py').read_text()
        self.assertIn('hooks=True', source)


if __name__ == '__main__':
    unittest.main()
