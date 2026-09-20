import unittest
from unittest.mock import patch
from publishing_v2.autopilot.sources import Sources, resolve_subject

class SubjectResolutionTests(unittest.TestCase):
    def test_resolves_verified_title_with_extra_query_words(self):
        rows = [{'title': 'Saudi Arabia national football team', 'id': 'wiki-1',
                 'source_type': 'encyclopedia', 'text': 'Retrieved subject context'}]
        self.assertEqual(resolve_subject('Saudi Arabia national football team squad Dawnis', rows),
                         {'name': rows[0]['title'], 'source_id': 'wiki-1'})

    def test_unrelated_or_ambiguous_search_results_are_not_promoted(self):
        rows = [{'title': t, 'id': str(i), 'source_type': 'encyclopedia', 'text': 'context'}
                for i, t in enumerate(['Simone Martini', 'Simeone Foundation'])]
        self.assertIsNone(resolve_subject('Diego Simeone', rows))
        self.assertIsNone(resolve_subject('Michelin', [dict(rows[0], title='Michelin Guide')]))

    def test_bad_first_page_does_not_fill_subject_pool(self):
        wrong = [dict(asset_id=str(i), title='Italian restaurant', license='CC0',
                      width=1600, height=1200) for i in range(5)]
        good = dict(asset_id='good', title='Diego Simeone portrait', license='CC0',
                    width=1600, height=1200)
        def search(query, limit=5, offset=0):
            return wrong if offset == 0 else [good] if offset == 5 else []
        with patch('publishing_v2.autopilot.sources.search_commons', side_effect=search) as api:
            rows = Sources().subject_images('Diego Simeone', 'Diego Simeone')
            self.assertEqual(rows, [good])
            self.assertLessEqual(api.call_count, 12)

    def test_retrieved_resolution_reaches_image_preflight(self):
        from publishing_v2.autopilot.runtime import Renderer
        candidate = {'id': 'c', 'url': 'https://www.bbc.com/news/a',
                     'editorial': {'research_query': 'Saudi Arabia national football team squad Dawnis'}}
        rows = [{'title': 'Saudi Arabia national football team', 'id': 'wiki-1',
                 'source_type': 'encyclopedia', 'text': 'Retrieved subject context'}]
        source = Sources()
        with patch('publishing_v2.autopilot.sources.fetch', return_value=b'a' * 300), \
             patch('publishing_v2.autopilot.sources.wiki', return_value=rows):
            source.research(candidate)
        with patch.object(source, 'subject_images', return_value=[]) as search:
            Renderer(object(), source).plan_visuals(candidate)
        search.assert_called_once_with(rows[0]['title'], rows[0]['title'])
        self.assertEqual(candidate['resolved_subject']['source_id'], 'wiki-1')

    def test_two_people_resolve_and_search_separately(self):
        from publishing_v2.autopilot.runtime import Renderer
        names = ['Jose Mourinho', 'Diego Simeone']
        candidate = {'editorial': {'research_query': 'rivalry', 'subjects': names}}
        def evidence(name):
            return [{'title': name, 'id': name, 'text': 'context', 'source_type': 'encyclopedia'}]
        source = Sources()
        with patch('publishing_v2.autopilot.sources.wiki', side_effect=evidence) as wiki:
            source.research(candidate)
            self.assertEqual([c.args[0] for c in wiki.call_args_list], names)
        def images(query, subject):
            return [{'asset_id': subject, 'title': subject, 'license': 'CC0'}]
        with patch.object(source, 'subject_images', side_effect=images) as search:
            self.assertEqual(len(Renderer(object(), source).plan_visuals(candidate)), 2)
            self.assertEqual([c.args for c in search.call_args_list], [(n, n) for n in names])
        with patch('publishing_v2.autopilot.sources.wiki', side_effect=[evidence(names[0]), []]):
            with self.assertRaisesRegex(ValueError, 'unresolved_editorial_subject'):
                source.research(candidate)
        self.assertNotIn('resolved_subjects', candidate)

    def test_invalid_subject_lists_hold(self):
        for names in [[], ['A', 'B', 'C'], ['A', 'a'], 'A', [None]]:
            with self.subTest(names=names), self.assertRaisesRegex(ValueError, 'invalid_editorial_subjects'):
                Sources().research({'editorial': {'subjects': names, 'research_query': 'A'}})

class RedirectResolutionTests(unittest.TestCase):
    def test_verified_redirect_resolves_without_accepting_unrelated_similar_title(self):
        row={'id':'wiki-12842989','title':'Saudi Arabian cuisine','source_type':'encyclopedia',
             'text':'Saudi Arabian cuisine is the cuisine of Saudi Arabia.',
             'verified_aliases':['Saudi cuisine']}
        self.assertEqual(resolve_subject('Saudi cuisine',[row]),
                         {'name':'Saudi Arabian cuisine','source_id':'wiki-12842989'})
        self.assertIsNone(resolve_subject('Saudi cuisine',[dict(row,verified_aliases=[])]))

    def test_wiki_uses_canonical_redirect_before_general_search(self):
        import json
        from publishing_v2.autopilot.sources import wiki
        response={'query':{'redirects':[{'from':'Saudi cuisine','to':'Saudi Arabian cuisine'}],
            'pages':{'12842989':{'pageid':12842989,'title':'Saudi Arabian cuisine','extract':'Verified food context'}}}}
        with patch('publishing_v2.autopilot.sources.fetch',return_value=json.dumps(response).encode()):
            rows=wiki('Saudi cuisine')
        self.assertEqual(rows[0]['verified_aliases'],['Saudi cuisine'])
        self.assertIsNotNone(resolve_subject('Saudi cuisine',rows))

class ConcreteSubjectTests(unittest.TestCase):
    def test_context_disambiguates_bisht_clothing_without_fuzzy_name_matching(self):
        rows=[{'id':'clothing','source_type':'encyclopedia','title':'Bisht (clothing)',
               'text':'A traditional cloak worn in Saudi Arabia.'},
              {'id':'surname','source_type':'encyclopedia','title':'Bisht (surname)',
               'text':'A surname used in India and Nepal.'}]
        self.assertEqual(resolve_subject('Bisht',rows,context='Bisht Saudi Arabia craft'),
                         {'name':'Bisht (clothing)','source_id':'clothing'})
        self.assertIsNone(resolve_subject('Bisht',rows))
        self.assertIsNone(resolve_subject('Different name',rows,context='Saudi Arabia'))
        rows[1]['text']='A person working in Saudi Arabia.'
        self.assertIsNone(resolve_subject('Bisht',rows,context='Bisht Saudi Arabia craft'))

    def test_abstract_compound_is_not_replaced_by_one_of_its_components(self):
        rows=[{'id':'aging','source_type':'encyclopedia','title':'Ageing', 'text':'Metabolism changes with age.'},
              {'id':'metabolism','source_type':'encyclopedia','title':'Metabolism','text':'Chemical processes in living organisms.'}]
        self.assertIsNone(resolve_subject('Aging and metabolism',rows,context='weight gain aging metabolism'))

    def test_research_uses_subject_context_and_records_rejection_without_searching_photos(self):
        bisht={'editorial':{'subjects':['Bisht'],'research_query':'Bisht Saudi Arabia craft'}}
        row={'id':'clothing','source_type':'encyclopedia','title':'Bisht (clothing)',
             'text':'A traditional cloak worn in Saudi Arabia.'}
        with patch('publishing_v2.autopilot.sources.wiki',return_value=[row]):
            Sources().research(bisht)
        self.assertEqual(bisht['resolved_subject']['name'],'Bisht (clothing)')
        abstract={'editorial':{'subjects':['Aging and metabolism'],'research_query':'weight gain aging metabolism'}}
        with patch('publishing_v2.autopilot.sources.wiki',return_value=[]):
            with self.assertRaisesRegex(ValueError,'unresolved_editorial_subject'):
                Sources().research(abstract)
        self.assertEqual(abstract['subject_resolution'][0]['query'],'Aging and metabolism')
        self.assertEqual(abstract['subject_resolution'][0]['status'],'needs_concrete_subject')

    def test_disambiguation_lookup_retrieves_same_name_object_instead_of_people(self):
        import json
        from urllib.parse import urlsplit, parse_qs
        from publishing_v2.autopilot.sources import wiki
        def fetched(url):
            params=parse_qs(urlsplit(url).query)
            if 'titles' in params:
                data={'query':{'pages':{'1':{'pageid':1,'title':'Bisht','extract':'Several meanings',
                                           'pageprops':{'disambiguation':''}}}}}
            elif 'list' in params:
                data={'query':{'search':[{'pageid':2}] if params['srsearch']==['intitle:Bisht'] else []}}
            else:
                data={'query':{'pages':{'2':{'pageid':2,'title':'Bisht (clothing)',
                                           'extract':'A cloak worn in Saudi Arabia.'}}}}
            return json.dumps(data).encode()
        with patch('publishing_v2.autopilot.sources.fetch',side_effect=fetched):
            result=resolve_subject('Bisht',wiki('Bisht'),context='Bisht Saudi Arabia craft')
        self.assertEqual(result,{'name':'Bisht (clothing)','source_id':'wiki-2'})
