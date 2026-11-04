"""Offline pinned selection must not depend on unrelated primary image success."""
import hashlib
import io
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from PIL import Image
from publishing_v2 import public_images
from publishing_v2.autopilot.sources import Sources
from publishing_v2.autopilot.runtime import Renderer


def photo(color):
    stream = io.BytesIO()
    Image.new('RGB', (1200, 800), color).save(stream, format='JPEG')
    return stream.getvalue()


def page(ident, **meta):
    return {'pageid': int(ident), 'title': 'File:Peregrine falcon ' + ident + '.jpg',
            'imageinfo': [{'mime': 'image/jpeg', 'url': 'https://upload.wikimedia.org/' + ident + '.jpg',
            'descriptionurl': 'https://commons.wikimedia.org/?curid=' + ident,
            'width': 1200, 'height': 800, 'extmetadata': {'LicenseShortName': {'value': 'CC0'}, **meta}}]}


class PinnedImageTests(unittest.TestCase):
    def setUp(self):
        self.plan = [{'asset_id': ident, 'purpose': 'Illustration'} for ident in ('32113801', '63746843', '63746844')]
        self.source = Sources(recovery=True, publication_only=True)
        self.candidate = {'editorial': {'research_query': 'Peregrine falcon'}, 'card_image_plan': self.plan}
        self.pages = [page(p['asset_id']) for p in self.plan]
        self.data = {p['asset_id']: photo(c) for p, c in zip(self.plan, ('red', 'green', 'blue'))}

    def screen(self, pages=None, data=None):
        with patch.object(public_images, 'get_json', return_value={'query': {'pages': self.pages if pages is None else pages}}), \
             patch.object(public_images, 'get_bytes', side_effect=lambda url: (data or self.data)[url.rsplit('/', 1)[-1][:-4]]):
            return Renderer(None, self.source).screen_visuals(self.candidate)

    def test_successful_primary_pool_cannot_hide_exact_pins(self):
        primary = public_images._commons_results({'query': {'pages': [page('11'), page('12')]}}, 2)
        self.source.primary_pools['Peregrine falcon'] = primary
        with patch.object(public_images, 'get_bytes', side_effect=[photo('yellow'), photo('purple')]):
            self.assertEqual(len(self.source.subject_images('Peregrine falcon', 'Peregrine falcon')), 2)
        with patch.object(self.source, 'subject_images', wraps=self.source.subject_images) as general:
            self.assertTrue(self.screen())
        general.assert_not_called()
        self.assertEqual({r['asset_id'] for r in self.candidate['visual_feasibility']}, set(self.data))
        for row in self.candidate['visual_feasibility']:
            self.assertEqual(row['sha256'], hashlib.sha256(self.data[row['asset_id']]).hexdigest())

    def test_catalog_reuses_pinned_preflight_not_general_search(self):
        self.assertTrue(self.screen())
        package = {'candidate': dict(self.candidate, id='candidate'),
                   'cards': [{'kind': 'information', 'image_query': 'Peregrine falcon'}] * 3}
        with patch.object(self.source, 'subject_images', return_value=[]) as general:
            catalog = Renderer(None, self.source).image_catalog(package)
        self.assertEqual({row['asset_id'] for row in catalog}, set(self.data))
        general.assert_not_called()

    def test_missing_pinned_asset_fails_without_substitution(self):
        self.assertFalse(self.screen(pages=self.pages[:2]))

    def test_rights_subject_small_original_and_invalid_pixels_rejected(self):
        for kind in ('rights', 'subject', 'small', 'pixels', 'duplicate'):
            self.setUp()
            if kind == 'rights': self.pages[0]['imageinfo'][0]['extmetadata']['Restrictions'] = {'value': 'Restricted'}
            if kind == 'subject': self.pages[0]['title'] = 'File:Unrelated bird.jpg'
            if kind == 'small': self.pages[0]['imageinfo'][0]['width'] = 100
            if kind == 'pixels': self.data['32113801'] = b'not an image'
            if kind == 'duplicate': self.data['32113801'] = self.data['63746843']
            with self.subTest(kind=kind): self.assertFalse(self.screen())

    def test_transport_failure_does_not_fallback_to_discovery(self):
        with patch.object(public_images, 'get_json', side_effect=public_images.ImageSourceError('http_403')), \
             patch.object(self.source, 'subject_images') as general:
            self.assertFalse(Renderer(None, self.source).screen_visuals(self.candidate))
        general.assert_not_called()

    def test_previous_subject_rejection_still_blocks_pin(self):
        self.source.image_memory.record('Peregrine falcon', {'provider': 'commons', 'asset_id': '32113801', 'original_url': 'https://upload.wikimedia.org/32113801.jpg'}, False)
        self.assertFalse(self.screen())

    def test_exact_lookup_supports_full_eight_card_bound(self):
        self.plan = [{'asset_id': str(i)} for i in range(1, 9)]
        self.candidate['card_image_plan'] = self.plan
        self.pages = [page(p['asset_id']) for p in self.plan]
        self.data = {p['asset_id']: photo((i * 25, 50, 100)) for i, p in enumerate(self.plan)}
        self.assertTrue(self.screen())
        self.assertEqual(len(self.candidate['visual_feasibility']), 8)

    def test_selected_plan_validates_before_any_io(self):
        for plan in ([{'asset_id': 'https://evil.test'}], [{'asset_id': '123', 'provider': 'other'}], self.plan * 3):
            with self.subTest(plan=plan), patch.object(public_images, 'get_json') as get:
                with self.assertRaises(ValueError): self.source.selected_images(plan, 'Peregrine falcon')
                get.assert_not_called()

    def test_exact_adapter_bounds_ids_and_ignores_unrequested_response(self):
        with patch.object(public_images, 'get_json', return_value={'query': {'pages': [page('123'), page('999')]}}) as get:
            self.assertEqual([r['asset_id'] for r in public_images.commons_ids(['123'])], ['123'])
            self.assertEqual(parse_qs(urlsplit(get.call_args.args[0]).query)['pageids'], ['123'])
        for ids in ([], ['0'], ['-1'], ['1|2'], ['01'], ['1'] * 9):
            with self.assertRaises(ValueError): public_images.commons_ids(ids)

if __name__ == '__main__': unittest.main()
