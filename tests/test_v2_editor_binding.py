import copy
import unittest
from unittest.mock import patch
from publishing_v2.autopilot import policy
import test_v2_autopilot as fixtures


def candidate():
    return {'id':'football','title':'مصعب الجوير يعتذر بعد استبعاده من المنتخب',
            'summary':'اعتذر مصعب الجوير لجمهوره بعد استبعاده من معسكر المنتخب.',
            'editorial':{'source_title':'مصعب الجوير يعتذر بعد استبعاده من المنتخب',
                'subjects':['Musab Al-Juwayer'], 'angle':'قصة مصعب الجوير',
                'why_now':'اعتذار الجوير اليوم',
                'subject_evidence':[{'subject':'Musab Al-Juwayer','mention':'مصعب الجوير',
                    'quote':'اعتذر مصعب الجوير لجمهوره بعد استبعاده من معسكر المنتخب.'}]}}

class BindingTests(unittest.TestCase):
    def test_matching_source_and_subject_pass(self):
        policy.validate_editor_binding(candidate())

    def test_football_angle_cannot_bind_to_yemen_article(self):
        row=candidate();row['title']='الجيش اليمني يوقف محاولات التوغل الحوثي غرب تعز'
        row['summary']='استعاد الجيش اليمني جبل نعمان غرب تعز.'
        with self.assertRaisesRegex(ValueError,'editor_source_title_mismatch'):
            policy.validate_editor_binding(row)
        row['editorial']['source_title']=row['title']
        with self.assertRaisesRegex(ValueError,'editor_subject_quote_not_in_source'):
            policy.validate_editor_binding(row)

    def test_translated_and_short_names_do_not_change_source_evidence(self):
        row = {'title':'Littler could boycott Dutch events over booing',
               'summary':'Luke Littler threatens a boycott of playing in the Netherlands.',
               'editorial':{'source_title':'Littler could boycott Dutch events over booing',
                   'subjects':['Luke Littler'], 'angle':'قصة ليتلر',
                   'why_now':'هدد بمقاطعة الفعاليات في هولندا',
                   'subject_evidence':[{'subject':'Luke Littler','mention':'Luke Littler',
                       'quote':'Luke Littler threatens a boycott of playing in the Netherlands.'}]}}
        policy.validate_editor_binding(row)
        row['editorial']['subject_evidence'][0]['mention'] = 'ليتلر'
        with self.assertRaisesRegex(ValueError, 'editor_subject_mention_not_grounded'):
            policy.validate_editor_binding(row)

    def test_short_arabic_presentation_preserves_full_source_name(self):
        row = candidate()
        row['editorial'].update(angle='قصة الجوير', why_now='اعتذاره اليوم')
        policy.validate_editor_binding(row)

    def test_every_subject_needs_actual_source_mention(self):
        for mutation in ['missing','extra_subject','invented_mention','altered_quote','short_quote']:
            row=candidate();edit=row['editorial']
            if mutation=='missing':edit.pop('subject_evidence')
            if mutation=='extra_subject':edit['subjects'].append('Another player')
            if mutation=='invented_mention':edit['subject_evidence'][0]['mention']='ليونيل ميسي'
            if mutation=='altered_quote':edit['subject_evidence'][0]['quote']='قصة أخرى لا وجود لها في المصدر الأصلي'
            if mutation=='short_quote':edit['subject_evidence'][0]['quote']='مصعب'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                policy.validate_editor_binding(row)

class BindingPipelineTests(unittest.TestCase):
    setUp=fixtures.PipelineTests.setUp
    pipeline=fixtures.PipelineTests.pipeline
    render=fixtures.PipelineTests.render
    publish=fixtures.PipelineTests.publish

    def test_bad_binding_rejected_before_source_research_then_next_candidate_used(self):
        pipeline=self.pipeline()
        original=self.agent.run
        def run(role,data,images=()):
            result=original(role,data,images)
            if role=='editor':result['candidates'][0]['source_title']='wrong article'
            return result
        self.agent.run=run
        researched=[]
        def research(row):
            researched.append(row['id']);return fixtures.evidence()
        with patch.object(pipeline.sources,'research',side_effect=research):
            result=pipeline.run('daily','shadow')
        self.assertEqual(researched,['b'])
        self.assertEqual(result['status'],'shadow_passed')
        rejected=[e for e in result['audit'] if e['event']=='candidate_rejected']
        self.assertEqual(rejected[0]['reason'],'editor_source_title_mismatch')
        self.assertEqual(rejected[0]['candidate_id'],'a')
