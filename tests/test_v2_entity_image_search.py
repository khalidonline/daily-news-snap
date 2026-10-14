# Owner 2026-09-26: "be smart and widen the search with several keywords".
# SAR's trains, stations and logo are on Commons, but a search for its English
# name, with a title filter on that name, found nothing publishable.
import unittest
from unittest.mock import patch

from publishing_v2.autopilot import sources
from publishing_v2.autopilot.sources import Sources, entity_profile, subject_metadata_matches

SUBJECT = 'Saudi Arabia Railways'


def wikidata(url):
    if 'Q777' in url and 'claims' in url:
        return {'entities': {'Q777': {
            'labels': {'en': {'value': SUBJECT}, 'ar': {'value': 'الخطوط الحديدية السعودية'}},
            'aliases': {'en': [{'value': 'SAR'}, {'value': 'Saudi Railway Company'}], 'ar': []},
            'claims': {
                'P18': [{'rank': 'normal', 'mainsnak': {'datavalue': {'value': 'SAR train Riyadh.jpg'}}}],
                'P154': [{'rank': 'normal', 'mainsnak': {'datavalue': {'value': 'SAR logo.svg'}}}],
                'P373': [{'rank': 'normal', 'mainsnak': {'datavalue': {'value': SUBJECT}}}],
                'P31': [{'rank': 'normal', 'mainsnak': {'datavalue': {'value': {'id': 'Q9'}}}}]}}}}
    return {'entities': {'Q9': {'labels': {'en': {'value': 'railway company'}}}}}


def row(asset, title):
    return {'provider': 'commons', 'asset_id': asset, 'title': title, 'description': '',
            'license': 'CC0', 'attribution_required': '', 'restrictions': '',
            'download_url': 'https://upload.wikimedia.org/' + asset, 'original_url': 'https://upload.wikimedia.org/' + asset}


class EntityProfileTests(unittest.TestCase):
    def test_profile_collects_names_files_category_and_typed_queries(self):
        with patch.object(sources, 'wiki_json', side_effect=wikidata):
            profile = entity_profile('Q777')
        self.assertIn('Saudi Railway Company', profile['names'])
        self.assertIn('الخطوط الحديدية السعودية', profile['names'])
        self.assertNotIn('SAR', profile['names'])            # Hong Kong SAR, search and rescue
        self.assertEqual(profile['files'], ['SAR train Riyadh.jpg', 'SAR logo.svg'])
        self.assertEqual(profile['categories'], [SUBJECT])
        self.assertIn(SUBJECT + ' train', profile['queries'])
        self.assertIn(SUBJECT + ' station', profile['queries'])

    def test_no_entity_means_no_widening(self):
        self.assertEqual(entity_profile(None), {'names': [], 'files': [], 'categories': [], 'queries': []})


class WidenedSearchTests(unittest.TestCase):
    def search(self, **patches):
        store = Sources(recovery=True, publication_only=True)
        store.subject_entities[SUBJECT] = 'Q777'
        defaults = {'wiki_json': wikidata, 'commons_files': lambda names, limit=5: [],
                    'search_commons_category': lambda c, limit=5: [], 'commons_subcategories': lambda c, limit=3: [],
                    'search_commons': lambda q, limit=5, offset=0: [], 'search_flickr': lambda *a, **k: [],
                    'search_met': lambda *a, **k: [], 'download_image': lambda r: b'bytes-' + r['asset_id'].encode()}
        defaults.update(patches)
        with patch.multiple(sources, **{k: v for k, v in defaults.items()}):
            found = store.subject_images(SUBJECT, SUBJECT)
        return store, found

    def test_entity_photo_and_logo_need_no_title_match(self):
        calls = []
        def files(names, limit=5):
            calls.append(names)
            return [row('1', 'File:Riyadh station at dusk.jpg'), row('2', 'File:Logo.svg.png')]
        store, found = self.search(commons_files=files)
        self.assertEqual(calls, [['SAR train Riyadh.jpg', 'SAR logo.svg']])
        self.assertEqual([r['asset_id'] for r in found], ['1', '2'])
        self.assertTrue(all(subject_metadata_matches(SUBJECT, r) for r in found))

    def test_category_descends_one_level_when_thin(self):
        def category(name, limit=5):
            return [row(name[-1], 'File:Locomotive ' + name[-1] + '.jpg')] if name != SUBJECT else []
        store, found = self.search(search_commons_category=category,
                                   commons_subcategories=lambda c, limit=3: ['Trains of SAR A', 'Stations of SAR B'])
        self.assertEqual(sorted(r['asset_id'] for r in found), ['A', 'B'])

    def test_other_names_widen_the_text_search(self):
        def search(q, limit=5, offset=0):
            if q == 'Saudi Railway Company':
                return [row('7', 'File:Saudi Railway Company locomotive.jpg'),
                        row('8', 'File:Saudi Railway Company station Hail.jpg')]
            return [row('9', 'File:Unrelated train in Hong Kong SAR.jpg')] if q == SUBJECT else []
        store, found = self.search(search_commons=search)
        self.assertEqual([r['asset_id'] for r in found], ['7', '8'])
        self.assertTrue(all(subject_metadata_matches(SUBJECT, r) for r in found))
        events = [e for e in store.image_diagnostics if e['provider'] == 'commons']
        self.assertEqual(events[0]['rejections'], {'subject': 1})

    def test_rights_filter_still_applies_to_entity_files(self):
        blocked = dict(row('1', 'File:x.jpg'), license='CC BY-SA 4.0')
        store, found = self.search(commons_files=lambda names, limit=5: [blocked])
        self.assertEqual(found, [])


if __name__ == '__main__':
    unittest.main()
