import tempfile
import unittest
from pathlib import Path
from publishing_v2 import public_images as images
from test_v2_public_images import candidate, jpeg


class FrameImagesTests(unittest.TestCase):
    def test_rejected_picture_continues_to_next_candidate(self):
        first = candidate(); first['asset_id'] = 'wrong'
        seen = []
        def review(asset, path, brief):
            seen.append(asset['asset_id'])
            self.assertEqual(path.read_bytes(), jpeg())
            return {'relevant': asset['asset_id'] != 'wrong', 'crop_suitable': True,
                    'historically_appropriate': True, 'reason': 'Checked frame subject and date'}
        with tempfile.TemporaryDirectory() as d:
            result = images.acquire('Voyager', d, sources=[('nasa', lambda q: [first, candidate()])],
                                    fetch=lambda u: jpeg(), frame_brief={'text': 'Voyager signal in 2013'}, reviewer=review)
            self.assertEqual(result['status'], 'screened_review_required')
            self.assertEqual(result['asset']['asset_id'], 'voyager')
            self.assertFalse(result['production_ready'])
            self.assertFalse(result['asset']['licensing_verified'])
            self.assertTrue((Path(d) / result['review_manifest']).exists())
        self.assertEqual(seen, ['wrong', 'voyager'])

    def test_missing_or_non_boolean_review_fails_closed(self):
        for decision in [{}, {'relevant': 'yes', 'crop_suitable': True, 'historically_appropriate': True, 'reason': 'ok'}]:
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as d:
                result = images.acquire('Voyager', d, sources=[('nasa', lambda q: [candidate()])], fetch=lambda u: jpeg(),
                                        frame_brief={'text': 'Voyager'}, reviewer=lambda *args: decision)
                self.assertEqual(result['status'], 'no_suitable_image')

    def test_review_binding_changes_when_frame_changes(self):
        results = []
        with tempfile.TemporaryDirectory() as d:
            for year in ['2013', '2026']:
                results.append(images.acquire('Voyager', d, sources=[('nasa', lambda q: [candidate()])], fetch=lambda u: jpeg(),
                    frame_brief={'text': 'Voyager', 'event_date': year}, reviewer=lambda *args: {
                        'relevant': True, 'crop_suitable': True, 'historically_appropriate': True, 'reason': 'Illustration identified'}))
            self.assertNotEqual(results[0]['review_manifest'], results[1]['review_manifest'])

    def test_reviewer_failure_tries_another_provider_without_leaking_error(self):
        def review(asset, *args):
            if asset['provider'] == 'commons': raise RuntimeError('SECRET')
            return {'relevant': True, 'crop_suitable': True, 'historically_appropriate': True, 'reason': 'Fits frame'}
        with tempfile.TemporaryDirectory() as d:
            result = images.acquire('Voyager', d, sources=[('commons', lambda q: [candidate('commons')]), ('nasa', lambda q: [candidate()])],
                fetch=lambda u: jpeg(), frame_brief={'text': 'Voyager'}, reviewer=review)
        self.assertEqual(result['asset']['provider'], 'nasa')
        self.assertNotIn('SECRET', str(result))
