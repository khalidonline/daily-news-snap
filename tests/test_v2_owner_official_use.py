import hashlib
import unittest
from unittest.mock import patch
from publishing_v2.autopilot.sources import Sources, reusable_image
from publishing_v2.publication import image_publication_eligible, validate_public_attribution
from test_v2_official_media import page


def discovered():
    from publishing_v2.official_images import search_official
    return search_official('Ceer Motors', fetch=lambda url, **k: (
        '<a href="/news/example/">Launch</a>' if url.endswith('/news/') else page()).encode())

class OwnerOfficialUseTests(unittest.TestCase):
    def test_owner_choice_enables_official_images_without_relabeling_copyright(self):
        with patch('publishing_v2.official_images.search_official', return_value=discovered()):
            image = Sources().official_images('Ceer Motors')[0]
        self.assertTrue(image_publication_eligible(image))
        self.assertTrue(reusable_image(image))
        self.assertEqual(image['license'], 'All rights reserved')
        self.assertFalse(image['licensing_verified'])
        self.assertEqual(image['rights_status'], 'owner_accepted_editorial_use')
        validate_public_attribution({'image': image})
        for changes in ({'source_url': 'https://evil.example/news/a'},
                        {'download_url': 'https://evil.example/a.jpg'},
                        {'asset_id': 'invented'}, {'owner_use_decision': 'model-approved'}):
            with self.subTest(changes=changes):
                self.assertFalse(image_publication_eligible(dict(image, **changes)))

    def test_official_images_pass_same_download_and_duplicate_checks(self):
        source = Sources(recovery=True, publication_only=True)
        with patch('publishing_v2.official_images.search_official', return_value=discovered()), \
             patch('publishing_v2.autopilot.sources.download_image', side_effect=[b'a', b'a', b'c']), \
             patch('publishing_v2.autopilot.sources.search_commons', return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_commons_category', return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_flickr', return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_met', return_value=[]):
            rows = source.subject_images('Ceer Motors', 'Ceer Motors')
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['sha256'] for r in rows}, {hashlib.sha256(x).hexdigest() for x in (b'a', b'c')})

    def test_review_credits_do_not_claim_official_images_are_public_domain(self):
        from publishing_v2.autopilot.credits import _blocks
        with patch('publishing_v2.official_images.search_official', return_value=discovered()):
            image = Sources().official_images('Ceer Motors')[0]
        text = ' '.join(t for t, _ in _blocks({'cards': [{'image': image}]}))
        self.assertIn('CEER', text)
        self.assertNotIn('public domain / CC0', text)

    def test_official_pool_prefers_varied_product_views_over_old_generic_images(self):
        from publishing_v2.official_images import varied_official_images
        titles = ['Image 1', 'Sedan Exterior', 'SUV Exterior', 'Interior Cockpit', 'SUV Doors Open', 'Car Charging']
        ordered = varied_official_images([{'title': t} for t in titles])
        self.assertEqual([r['title'] for r in ordered[:4]],
                         ['Sedan Exterior', 'Interior Cockpit', 'SUV Doors Open', 'Car Charging'])
