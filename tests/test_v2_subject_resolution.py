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
