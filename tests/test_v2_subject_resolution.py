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
