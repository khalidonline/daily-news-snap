import unittest
from datetime import timedelta
from publishing_v2.autopilot.candidate_memory import CandidateMemory
from publishing_v2.autopilot.evidence import hydrate_editor
from publishing_v2.autopilot.eligibility import routine_trigger_rejection
import test_v2_autopilot as fixtures
from test_v2_editor_source_fields import source, selection


class MemoryTests(unittest.TestCase):
    def test_unchanged_news_is_skipped_but_updates_expiry_and_repairs_retry(self):
        store = fixtures.MemoryStore()
        now = fixtures.NOW
        memory = CandidateMemory(store, lambda: now)
        candidate = {'id':'one','url':'https://example.com/a','title':'News','summary':'Original'}
        memory.record(candidate, 'sensitive_or_uncertain_topic', 'old')
        restored = CandidateMemory(store, lambda: now)
        self.assertEqual(restored.reason(dict(candidate, id='new', published_at='new'), 'new-engine'),
                         'sensitive_or_uncertain_topic')
        self.assertIsNone(restored.reason(dict(candidate, summary='Updated reporting'), 'old'))
        now += timedelta(days=1)
        self.assertIsNone(restored.reason(candidate, 'old'))
        memory.record(candidate, 'editor_subject_mention_not_grounded', 'old')
        self.assertIsNone(memory.reason(candidate, 'fixed-engine'))
        self.assertIsNotNone(memory.reason(candidate, 'old'))

    def test_transient_errors_are_not_remembered(self):
        memory = CandidateMemory(fixtures.MemoryStore(), lambda: fixtures.NOW)
        memory.record({'id':'a','title':'a'}, 'RuntimeError', 'one')
        self.assertEqual(memory.rows, {})

    def test_wrong_field_recovers_only_literal_original_name(self):
        candidate, choice = source(), selection()
        choice['subject_evidence'][0]['source_field'] = 'title'
        result = hydrate_editor(choice, candidate)
        self.assertEqual(result['subject_evidence'][0]['quote'], candidate['summary'])
        choice['subject_evidence'][0]['mention'] = 'Roshn Front'
        with self.assertRaisesRegex(ValueError, 'mention_not_grounded'):
            hydrate_editor(choice, candidate)

    def test_early_filters_preserve_substantive_events(self):
        for title in ['نائب أمير الشرقية يستقبل مدير فرع هيئة عقارات الدولة بالدمام',
                      "Martha’s Rule to expand to A&E", 'Earl Spencer reveals child abuse']:
            self.assertIsNotNone(routine_trigger_rejection({'title':title}))
        for title in ['أمير الشرقية يفتتح مصنع السيارات', 'المتحف يستقبل مليون زائر',
                      'Mark Wood retires from cricket']:
            self.assertIsNone(routine_trigger_rejection({'title':title}))


class PipelineMemoryTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    pipeline = fixtures.PipelineTests.pipeline
    render = fixtures.PipelineTests.render
    publish = fixtures.PipelineTests.publish

    def test_previous_rejections_stop_before_paid_roles_across_engines(self):
        pipeline = self.pipeline()
        memory = CandidateMemory(fixtures.MemoryStore(), lambda: fixtures.NOW)
        for candidate in pipeline.sources.discover('daily', fixtures.NOW):
            memory.record(candidate, 'sensitive_or_uncertain_topic', 'old-engine')
        pipeline.candidate_memory = memory
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertEqual(self.agent.calls, [])
        self.assertEqual(len(result['eligibility_rejections']), 2)

    def test_memory_write_failure_stops_instead_of_spending_on_next_candidate(self):
        from publishing_v2.autopilot.pipeline import PersistenceError
        pipeline = self.pipeline()
        class Broken:
            def reason(self, *args): return None
            def record(self, *args): raise OSError('unavailable')
        pipeline.candidate_memory = Broken()
        pipeline.sources.attention = lambda candidate: []
        with self.assertRaises(PersistenceError):
            pipeline.run('daily', 'shadow')
        self.assertEqual(self.agent.calls, ['editor'])
