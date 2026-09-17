import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from publishing_v2 import public_images
from publishing_v2.autopilot.sources import Sources


class MediaRecoveryTests(unittest.TestCase):
    def test_long_local_brief_recovers_subject_and_reuses_cache(self):
        good = {'asset_id': 'jeddah', 'license': 'CC0', 'title': 'File:Jeddah.jpg'}
        calls = []
        def search(query, limit=5, offset=0):
            calls.append((query, offset))
            return [good] if query == 'Jeddah' else []
        source = Sources()
        with patch('publishing_v2.autopilot.sources.search_commons', side_effect=search):
            self.assertEqual(source.images('Jeddah traditional historic buildings street daylight'), [good])
            count = len(calls)
            self.assertEqual(source.images('Jeddah traditional historic buildings street daylight'), [good])
            self.assertEqual(len(calls), count)
            self.assertEqual(source.images('Jeddah'), [good])
            self.assertEqual(len(calls), count)
        self.assertLessEqual(count, 12)

    def test_deeper_pool_recovers_pd_when_first_page_contains_filtered_formats(self):
        good = {'asset_id': 'palm', 'license': 'Public domain'}
        def search(query, limit=5, offset=0):
            if query == 'date palm' and offset == 5:
                return [good]
            return [{'asset_id': str(i), 'license': 'CC BY-SA 4.0'} for i in range(4)]
        with patch('publishing_v2.autopilot.sources.search_commons', side_effect=search):
            self.assertEqual(Sources().images('date palm'), [good])

    def test_sparse_first_page_does_not_hide_additional_eligible_choices(self):
        one = {'asset_id': 'one', 'license': 'Public domain'}
        two = {'asset_id': 'two', 'license': 'CC0'}
        def search(query, limit=5, offset=0):
            if query == 'Jeddah' and offset == 0:
                return [one]
            if 'haswbstatement' in query and offset == 0:
                return [one, two]
            return []
        with patch('publishing_v2.autopilot.sources.search_commons', side_effect=search):
            self.assertEqual(Sources().images('Jeddah'), [one, two])

    def test_empty_results_are_cached_and_searches_bounded(self):
        with patch('publishing_v2.autopilot.sources.search_commons', return_value=[]) as search:
            source = Sources()
            self.assertEqual(source.images('completely unknown very long photographic subject query'), [])
            count = search.call_count
            self.assertEqual(source.images('completely unknown very long photographic subject query'), [])
            self.assertEqual(search.call_count, count)
            self.assertLessEqual(count, 12)

    def test_commons_offset_is_bounded_and_used_in_request(self):
        with patch.object(public_images, 'get_json', return_value={}) as get:
            self.assertEqual(public_images.search_commons('Jeddah', offset=5), [])
            params = parse_qs(urlsplit(get.call_args.args[0]).query)
            self.assertEqual(params['gsroffset'], ['5'])
            for offset in [-1, 21, True, '5']:
                with self.assertRaises(ValueError):
                    public_images.search_commons('Jeddah', offset=offset)

    def test_empty_query_does_not_browse_unrelated_images(self):
        with patch('publishing_v2.autopilot.sources.search_commons') as search:
            self.assertEqual(Sources().images('   '), [])
            search.assert_not_called()


if __name__ == '__main__': unittest.main()
