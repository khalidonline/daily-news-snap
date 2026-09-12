import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from publishing_v2 import public_images as images


def jpeg():
    out = io.BytesIO()
    Image.new('RGB', (1600, 1000), 'blue').save(out, format='JPEG')
    return out.getvalue()


def candidate(provider='nasa'):
    return {'provider': provider, 'asset_id': 'voyager', 'source_url': 'https://images.nasa.gov/details/voyager',
            'download_url': 'https://images-assets.nasa.gov/image/voyager/voyager~large.jpg',
            'title': 'Voyager', 'description': 'Spacecraft', 'credit': 'NASA', 'license': 'review_required',
            'license_url': 'https://www.nasa.gov/nasa-brand-center/images-and-media/', 'date_created': '2013'}


class PublicImagesTests(unittest.TestCase):
    def test_network_rejects_unapproved_hosts_and_credentials(self):
        for url in ['http://images-assets.nasa.gov/a.jpg', 'https://example.com/a',
                    'https://images-assets.nasa.gov.evil.test/a', 'https://user@images-assets.nasa.gov/a',
                    'https://images-assets.nasa.gov:444/a']:
            with self.subTest(url=url), self.assertRaises(images.ImageSourceError):
                images.validate_url(url)

    def test_commons_preserves_license_and_credit_without_approving(self):
        response = {'query': {'pages': [{'pageid': 1, 'title': 'File:Voyager.jpg', 'imageinfo': [{
            'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/Voyager.jpg',
            'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Voyager.jpg', 'mime': 'image/jpeg',
            'extmetadata': {'Artist': {'value': '<b>NASA</b>'}, 'LicenseShortName': {'value': 'CC BY 4.0'},
                            'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by/4.0/'}}}]}]}}
        with patch.object(images, 'get_json', return_value=response):
            item = images.search_commons('Voyager')[0]
        self.assertEqual(item['credit'], 'NASA')
        self.assertEqual(item['license'], 'CC BY 4.0')
        self.assertFalse(item['licensing_verified'])

    def test_nasa_keeps_copyright_review_required(self):
        search = {'collection': {'items': [{'data': [{'nasa_id': 'voyager', 'title': 'Voyager',
                   'description': 'Artist concept, third-party credit', 'media_type': 'image'}]}]}}
        asset = {'collection': {'items': [{'href': candidate()['download_url']}]}}
        with patch.object(images, 'get_json', side_effect=[search, asset]):
            item = images.search_nasa('Voyager')[0]
        self.assertEqual(item['license'], 'review_required')
        self.assertFalse(item['licensing_verified'])

    def test_invalid_or_tiny_image_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(images.ImageSourceError):
                images.store_candidate(candidate(), Path(d), fetch=lambda u: b'<html>denied</html>')
            tiny = io.BytesIO()
            Image.new('RGB', (10, 10)).save(tiny, format='PNG')
            with self.assertRaises(images.ImageSourceError):
                images.store_candidate(candidate(), Path(d), fetch=lambda u: tiny.getvalue())
            self.assertFalse(list(Path(d).glob('*.json')))

    def test_store_retains_original_bytes_hash_provenance_and_no_approval(self):
        with tempfile.TemporaryDirectory() as d:
            result = images.store_candidate(candidate(), Path(d), fetch=lambda u: jpeg())
            self.assertEqual((Path(d) / result['file']).read_bytes(), jpeg())
            receipt = json.loads((Path(d) / result['manifest']).read_text())
            self.assertEqual(receipt['credit'], 'NASA')
            self.assertFalse(receipt['visual_approved'])
            self.assertFalse(receipt['licensing_verified'])
            self.assertEqual(receipt['width'], 1600)

    def test_source_failure_recovers_with_independent_provider(self):
        def failed(q):
            raise images.ImageSourceError('http_403')
        with tempfile.TemporaryDirectory() as d:
            report = images.acquire('Voyager', Path(d), sources=[('commons', failed), ('nasa', lambda q: [candidate()])], fetch=lambda u: jpeg())
        self.assertEqual(report['status'], 'downloaded_review_required')
        self.assertEqual(report['asset']['provider'], 'nasa')
        self.assertEqual(report['attempts'][0]['status'], 'source_failed')
        self.assertFalse(report['production_ready'])

    def test_failed_download_tries_next_candidate(self):
        first = candidate(); first['download_url'] += '?broken'
        def fetch(url):
            if url.endswith('?broken'): raise images.ImageSourceError('http_404')
            return jpeg()
        with tempfile.TemporaryDirectory() as d:
            report = images.acquire('Voyager', Path(d), sources=[('nasa', lambda q: [first, candidate()])], fetch=fetch)
        self.assertEqual(report['status'], 'downloaded_review_required')
        self.assertEqual(report['attempts'][0]['status'], 'candidate_failed')

    def test_all_sources_failed_is_not_success_and_errors_are_sanitized(self):
        def fail(q): raise RuntimeError('SECRET-SENTINEL')
        with tempfile.TemporaryDirectory() as d:
            report = images.acquire('Voyager', Path(d), sources=[('commons', fail)])
        self.assertEqual(report['status'], 'no_download')
        self.assertNotIn('SECRET-SENTINEL', json.dumps(report))

if __name__ == '__main__': unittest.main()
