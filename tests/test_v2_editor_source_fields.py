import copy
import unittest
from publishing_v2.autopilot import evidence, policy
import test_v2_autopilot as fixtures


def source():
    return {'id': 'jeddah', 'title': 'جدة تختتم العروض الجوية',
            'summary': 'اختتمت محافظة جدة ، اليوم الأحد، العروض الجوية ب واجهة روشن البحرية .'}


def selection():
    return {'id': 'jeddah', 'evidence_format': 'source-fields-v1',
            'why_saudi': 'مكان معروف في جدة', 'why_now': 'اختتام العروض في ٢٠ سبتمبر',
            'angle': 'قصة الواجهة البحرية', 'share_reason': 'قصة مكان قريب من الناس',
            'research_query': 'Roshn Front Jeddah',
            'subject_evidence': [{'subject': 'Roshn Front (Jeddah)',
                                  'mention': 'واجهة روشن البحرية', 'source_field': 'summary'}]}


class SourceFieldsTests(unittest.TestCase):
    def hydrate(self, choice, candidate):
        self.assertTrue(callable(getattr(evidence, 'hydrate_editor', None)),
                        'Editor must resolve evidence from original source fields')
        return evidence.hydrate_editor(choice, candidate)

    def test_jeddah_source_spacing_and_single_subject_name_are_preserved(self):
        candidate, choice = source(), selection()
        original = copy.deepcopy(choice)
        result = self.hydrate(choice, candidate)
        self.assertEqual(result['subject_evidence'][0]['quote'], candidate['summary'])
        self.assertEqual(result['subjects'], ['Roshn Front (Jeddah)'])
        self.assertEqual(result['source_title'], candidate['title'])
        policy.validate_editor_binding(dict(candidate, editorial=result))
        self.assertEqual(choice, original)

    def test_title_field_is_resolved_without_model_transcription(self):
        choice = selection()
        choice['subject_evidence'] = [{'subject': 'Jeddah', 'mention': 'جدة', 'source_field': 'title'}]
        result = self.hydrate(choice, source())
        self.assertEqual(result['subject_evidence'][0]['quote'], source()['title'])
        policy.validate_editor_binding(dict(source(), editorial=result))

    def test_exact_copied_source_field_recovers_without_changing_evidence(self):
        for field, mention in [('title', 'جدة'), ('summary', 'واجهة روشن البحرية')]:
            candidate, choice = source(), selection()
            choice['subject_evidence'][0].update(source_field=candidate[field], mention=mention)
            original = copy.deepcopy(choice)
            result = self.hydrate(choice, candidate)
            self.assertEqual(result['subject_evidence'][0]['quote'], candidate[field])
            self.assertEqual(choice, original)

    def test_copied_field_never_accepts_partial_paraphrased_or_other_source_text(self):
        for value in [source()['summary'][:20], source()['summary'] + ' زيادة',
                      source()['summary'].replace('جدة', 'الرياض'), '', [], None]:
            choice = selection()
            choice['subject_evidence'][0]['source_field'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'invalid_editor_source_field'):
                self.hydrate(choice, source())

    def test_exact_copied_field_still_requires_grounded_mention(self):
        choice = selection()
        choice['subject_evidence'][0].update(source_field=source()['summary'], mention='الرياض')
        with self.assertRaisesRegex(ValueError, 'editor_subject_mention_not_grounded'):
            self.hydrate(choice, source())

    def test_wrong_candidate_or_invented_evidence_cannot_be_hydrated(self):
        for change in ('id', 'field', 'mention', 'quote', 'subjects', 'title', 'duplicate', 'format'):
            choice = selection()
            if change == 'id': choice['id'] = 'another'
            if change == 'field': choice['subject_evidence'][0]['source_field'] = 'url'
            if change == 'mention': choice['subject_evidence'][0]['mention'] = 'الرياض'
            if change == 'quote': choice['subject_evidence'][0]['quote'] = 'invented'
            if change == 'subjects': choice['subjects'] = ['Another subject']
            if change == 'title': choice['source_title'] = 'another title'
            if change == 'duplicate': choice['subject_evidence'] *= 2
            if change == 'format': choice['evidence_format'] = 'unknown'
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.hydrate(choice, source())


class SourceFieldsPipelineTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    pipeline = fixtures.PipelineTests.pipeline
    render = fixtures.PipelineTests.render
    publish = fixtures.PipelineTests.publish

    def test_bad_new_format_is_rejected_then_next_candidate_is_used(self):
        original = self.agent.run
        def run(role, data, images=()):
            result = original(role, data, images)
            if role == 'editor':
                choice = result['candidates'][0]
                choice['evidence_format'] = 'source-fields-v1'
                choice.pop('subjects'); choice.pop('source_title')
                for row in choice['subject_evidence']:
                    row.pop('quote'); row['source_field'] = 'url'
            return result
        self.agent.run = run
        result = self.pipeline().run('daily', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertEqual(result['candidate']['id'], 'b')
        self.assertTrue(any(e.get('reason') == 'invalid_editor_source_field'
                            for e in result['audit']))

    def test_new_editor_contract_reaches_existing_review_gates(self):
        original = self.agent.run
        def run(role, data, images=()):
            result = original(role, data, images)
            if role == 'editor':
                for choice in result['candidates']:
                    choice['evidence_format'] = 'source-fields-v1'
                    choice.pop('subjects'); choice.pop('source_title')
                    for row in choice['subject_evidence']:
                        row.pop('quote'); row['source_field'] = 'summary'
            return result
        self.agent.run = run
        result = self.pipeline().run('daily', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertEqual(result['candidate']['editorial']['subjects'], ['Jeddah'])
