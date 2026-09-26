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


class CheapRejectionTests(unittest.TestCase):
    """2026-09-26 test run: camels died over one formal word and SAR over photos,
    both after research and writing were paid for."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def pipeline(self, agent, render):
        return Pipeline(agent=agent, sources=FakeSources(), render=render, store=MemoryStore(),
                        publish=lambda p, paths: None, output=Path(self.temp.name), now=lambda: NOW)

    @staticmethod
    def paths(package, output):
        output.mkdir(parents=True, exist_ok=True)
        result = []
        for i, _ in enumerate(package['cards']):
            path = output / f'{i}.jpg'
            path.write_bytes(f'pixels {i}'.encode())
            result.append(path)
        return result

    def test_formal_word_is_patched_not_fatal(self):
        class Formal(FakeAgent):
            def run(self, role, data, images=()):
                if role == 'writer':
                    self.calls.append(role)
                    bad = draft()
                    bad['cards'][2]['body'] = 'وصار معروفاً بين الناس'
                    return bad
                if role == 'card_repair':
                    self.calls.append(role)
                    self.repair = data['repair_indices']
                    fixed = copy.deepcopy(data['draft']['cards'][2])
                    fixed['body'] = 'وصار مشهور بين الناس'
                    return {'patches': [{'index': 2, 'card': fixed}]}
                return super().run(role, data, images)
        agent = Formal()
        result = self.pipeline(agent, self.paths).run('daily', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertEqual(agent.repair, [2])
        self.assertEqual(agent.calls.count('writer'), 1)

    def test_structural_draft_fault_still_rejects(self):
        package = draft()
        package['cards'][0]['claim_ids'] = ['c9']
        self.assertEqual(policy.style_repair_indices(package), [])

    def test_visual_screen_rejects_before_paid_research(self):
        agent = FakeAgent()
        render = self.paths
        class Render:
            def __call__(self, package, output): return render(package, output)
            def screen_visuals(self, candidate): return False
        result = self.pipeline(agent, Render()).run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertNotIn('researcher', agent.calls)
        reasons = [e.get('reason') for e in result['audit'] if e['event'] == 'candidate_rejected']
        self.assertTrue(reasons and all(r == 'insufficient_subject_visuals_before_research' for r in reasons))

    def test_screen_uses_plan_visuals_filters_without_model_calls(self):
        from publishing_v2.autopilot.runtime import Renderer
        class Sources:
            def prime_images(self, candidate, subject): self.primed = subject
            def subject_images(self, subject, query):
                return [{'asset_id': 'a', 'title': 'Saudi Railway train', 'license': 'CC0'},
                        {'asset_id': 'b', 'title': 'Saudi Railway station', 'license': 'CC BY-SA 4.0'}]
        class NoAgent:
            def run(self, *a, **k): raise AssertionError('screen must not call a model')
        renderer = Renderer(NoAgent(), Sources())
        candidate = {'resolved_subjects': [{'name': 'Saudi Railway'}]}
        self.assertFalse(renderer.screen_visuals(candidate))   # the BY-SA row is not publishable
        renderer.sources.subject_images = lambda s, q: [
            {'asset_id': x, 'title': 'Saudi Railway train ' + x, 'license': 'CC0'} for x in 'ab']
        self.assertTrue(renderer.screen_visuals(candidate))


class PublisherImageTests(unittest.TestCase):
    ITEM = '''<item xmlns:media="http://search.yahoo.com/mrss/">
      <enclosure url="https://www.alyaum.com/uploads/sar.jpg" type="image/jpeg"/>
      <enclosure url="https://www.alyaum.com/audio.mp3" type="audio/mpeg"/>
      <media:content url="https://www.alyaum.com/uploads/sar2.jpg" medium="image"/>
      <description>&lt;img src="https://www.alyaum.com/uploads/sar3.jpg"&gt; نص</description>
    </item>'''

    def test_feed_item_photos_are_extracted(self):
        from xml.etree import ElementTree
        from publishing_v2.autopilot.sources import feed_images
        self.assertEqual(feed_images(ElementTree.fromstring(self.ITEM)), [
            'https://www.alyaum.com/uploads/sar.jpg', 'https://www.alyaum.com/uploads/sar2.jpg',
            'https://www.alyaum.com/uploads/sar3.jpg'])

    def test_blocked_article_page_falls_back_to_browser_then_feed_photo(self):
        from urllib.error import HTTPError
        from publishing_v2.autopilot import sources
        url = 'https://www.alyaum.com/articles/1/sar'
        candidate = {'id': 'x', 'url': url, 'published_at': '2026-09-26T09:00:00+00:00'}
        store = sources.Sources(recovery=True, publication_only=True)
        store.feed_images[('x', url, candidate['published_at'])] = ['https://www.alyaum.com/uploads/sar.jpg']
        agents_seen = []
        def blocked(u, user_agent='DailyNewsSnap/2.0 (editorial research)'):
            agents_seen.append(user_agent)
            raise HTTPError(u, 403, 'Forbidden', {}, None)
        with patch.object(sources, 'fetch', side_effect=blocked):
            store.attention(candidate)
        self.assertEqual(agents_seen[-1], sources.BROWSER_UA)
        rows = sources.page_images(store.article_html[url], url, 'Saudi Railway', kind='article')
        self.assertEqual([r['original_url'] for r in rows], ['https://www.alyaum.com/uploads/sar.jpg'])
        self.assertTrue(all(sources.owner_primary_use(r) for r in rows))
