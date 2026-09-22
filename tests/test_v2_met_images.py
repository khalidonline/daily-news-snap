import unittest
from unittest.mock import patch
from publishing_v2 import met_images as met
from publishing_v2.autopilot.sources import Sources


def object_row(i=443173, **updates):
    row = dict(objectID=i, isPublicDomain=True, title='Coffee Pot', country='Turkey',
               culture='', objectDate='1809–60', objectURL=f'https://www.metmuseum.org/art/collection/search/{i}',
               primaryImage=f'https://images.metmuseum.org/CRDImages/is/original/{i}.jpg')
    row.update(updates)
    return row


class MetImagesTests(unittest.TestCase):
    def search(self, rows, query='Coffee pot'):
        with patch.object(met, 'get_json', side_effect=[{'objectIDs': list(range(1,len(rows)+1))}] + rows):
            return met.search_met(query, limit=len(rows))

    def test_preserves_origin_date_and_public_license(self):
        rows = self.search([object_row(1)])
        self.assertEqual(rows[0]['asset_id'], 'met:1')
        self.assertEqual(rows[0]['license'], 'CC0')
        self.assertIn('Turkey', rows[0]['description'])
        self.assertIn('1809–60', rows[0]['description'])
        self.assertEqual(rows[0]['attribution_required'], 'false')

    def test_rejects_private_missing_images_and_wrong_object_identity(self):
        self.assertEqual(self.search([object_row(1,isPublicDomain='true'), object_row(2,primaryImage=''), object_row(99)]), [])

    def test_rejects_foreign_or_credentialed_image_hosts(self):
        for url in ['https://evil.test/a.jpg','https://images.metmuseum.org@evil.test/a.jpg',
                    'https://u:p@images.metmuseum.org/a.jpg','http://images.metmuseum.org/a.jpg']:
            with self.subTest(url=url):
                self.assertEqual(self.search([object_row(1,primaryImage=url)]), [])

    def test_modern_people_do_not_query_museum(self):
        with patch.object(met, 'get_json', side_effect=AssertionError('network')):
            self.assertEqual(met.search_met('Mohamed Salah'), [])

    def test_search_is_paginated_bounded_and_deduplicated(self):
        urls=[]
        def fetch(url):
            urls.append(url)
            return {'objectIDs':[1,1,2,3,4]} if '/search?' in url else object_row(int(url.rsplit('/',1)[1]))
        with patch.object(met,'get_json',side_effect=fetch):
            rows=met.search_met('Coffee pot',limit=2)
        self.assertEqual([r['asset_id'] for r in rows],['met:1','met:2'])
        self.assertEqual(len(urls),3)
        self.assertIn('/v1.1/search?',urls[0])
        self.assertIn('limit=2',urls[0])

    def test_deadline_prevents_requests(self):
        with patch.object(met,'get_json',side_effect=AssertionError('network')):
            self.assertEqual(met.search_met('Coffee pot',deadline=0),[])

    def test_one_bad_record_does_not_hide_later_valid_record(self):
        self.assertEqual([r['asset_id'] for r in self.search([None,object_row(2)])],['met:2'])

    def test_recovery_uses_met_but_keeps_subject_and_duplicate_gates(self):
        rows=[dict(object_row(),provider='met',asset_id='met:1',license='CC0',
                   title='Coffee Pot',description='Turkey',download_url='https://images.metmuseum.org/a.jpg'),
              dict(provider='met',asset_id='met:2',license='CC0',title='Unrelated sword',download_url='https://images.metmuseum.org/b.jpg')]
        with patch('publishing_v2.autopilot.sources.search_commons',return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_commons_category',return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_flickr',return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_met',return_value=rows), \
             patch('publishing_v2.autopilot.sources.download_image',return_value=b'validated-image'):
            found=Sources(recovery=True,publication_only=True).recover_images('Coffee pot','Coffee pot')
        self.assertEqual([r['asset_id'] for r in found],['met:1'])

    def test_commons_thumbnail_and_met_original_are_one_source_image(self):
        commons=dict(provider='commons',asset_id='777',title='Coffee Pot',license='CC0',
            download_url='https://upload.wikimedia.org/thumb.jpg',
            rights_links='https://www.metmuseum.org/art/collection/search/443173')
        original=dict(commons,provider='met',asset_id='met:443173',
            source_url='https://www.metmuseum.org/art/collection/search/443173',
            download_url='https://images.metmuseum.org/CRDImages/is/original/DP222480.jpg')
        with patch('publishing_v2.autopilot.sources.search_commons',return_value=[commons]), \
             patch('publishing_v2.autopilot.sources.search_commons_category',return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_flickr',return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_met',return_value=[original]), \
             patch('publishing_v2.autopilot.sources.download_image',side_effect=lambda r:r['asset_id'].encode()):
            found=Sources(recovery=True,publication_only=True).recover_images('Coffee pot','Coffee pot')
        self.assertEqual([r['asset_id'] for r in found],['met:443173'])
        self.assertEqual(found[0]['origin_key'],'met:443173')

if __name__=='__main__': unittest.main()
