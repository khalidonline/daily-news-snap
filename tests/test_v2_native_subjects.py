import json
import unittest
from unittest.mock import patch
from publishing_v2.autopilot import sources


def candidate():
    title='البشت في الأحساء.. حرفة عريقة وهوية وطنية'
    return {'id':'bisht','title':title,'summary':'صناعة البشت في الأحساء حرفة قديمة.',
            'editorial':{'source_title':title,'subjects':['Al-Ahsa'],'research_query':'Al-Ahsa',
                'angle':'حرفة البشت في الأحساء','why_now':'تقرير جديد',
                'subject_evidence':[{'subject':'Al-Ahsa','mention':'الأحساء','quote':title}]}}

class NativeSubjectTests(unittest.TestCase):
    def test_native_source_title_recovers_failed_english_lookup(self):
        row=candidate()
        def wiki(query, **kwargs):
            if query=='الأحساء':
                self.assertEqual(kwargs,{'language':'ar','exact_only':True})
                return [{'id':'wiki-ar-746248','title':'الأحساء','verified_aliases':['الأحساء'],
                         'text':'الأحساء مدينة سعودية','source_type':'encyclopedia'}]
            return []
        with patch.object(sources,'wiki',side_effect=wiki):
            evidence=sources.Sources().research(row)
        self.assertEqual(row['resolved_subject']['name'],'الأحساء')
        self.assertEqual(row['subject_resolution'][0]['resolution_query'],'الأحساء')
        self.assertEqual(evidence[0]['id'],'wiki-ar-746248')

    def test_mismatched_source_cannot_supply_native_fallback(self):
        row=candidate();row['title']='خبر مختلف عن اليمن'
        with patch.object(sources,'wiki',return_value=[]) as wiki:
            with self.assertRaisesRegex(ValueError,'unresolved_editorial_subject'):
                sources.Sources().research(row)
        self.assertEqual(wiki.call_count,1)

    def test_native_redirect_retains_language_and_does_not_collide_with_english_id(self):
        payload={'query':{'pages':{'123':{'pageid':123,'title':'الأحساء','extract':'معلومات عن الأحساء'}}}}
        with patch.object(sources,'fetch',return_value=json.dumps(payload).encode()):
            row=sources.wiki('الأحساء',language='ar',exact_only=True)[0]
        self.assertEqual(row['id'],'wiki-ar-123')
        self.assertEqual(row['url'],'https://ar.wikipedia.org/?curid=123')

    def test_missing_or_ambiguous_native_title_never_runs_broad_search(self):
        for page in [{'pageid':-1,'missing':''},
                     {'pageid':1,'extract':'different people','pageprops':{'disambiguation':''}}]:
            with patch.object(sources,'fetch',return_value=json.dumps({'query':{'pages':{'1':page}}}).encode()) as fetch:
                self.assertEqual(sources.wiki('اسم',language='ar',exact_only=True),[])
                self.assertEqual(fetch.call_count,1)
