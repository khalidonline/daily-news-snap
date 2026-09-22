import json
import unittest
from unittest.mock import patch
from publishing_v2.autopilot.sources import Sources
from publishing_v2.autopilot.runtime import Renderer
from publishing_v2.publication import image_publication_eligible

ARTICLE = 'https://ceermotors.com/news/example/'

def page():
    files = [{'assetType': 'image', 'title': name, 'file': {
        'documentId': str(i), 'url': 'https://assets.ceermotors.com/uploads/assets/' + str(i) + '.jpg',
        'mime': 'image/jpeg', 'width': 4000, 'height': 2250}}
        for i, name in enumerate(['EXOBOT Sedan Exterior', 'EXOBOT Interior', 'EXOBOT Charging'])]
    files += [dict(files[0]), {'assetType': 'image', 'title': 'tracking', 'file': {
        'url': 'https://evil.example/image.jpg', 'mime': 'image/jpeg', 'width': 4000, 'height': 2250}}]
    payload = '1:' + json.dumps({'mediaAssets': {'assets': files}})
    return '<script>self.__next_f.push(' + json.dumps([1, payload]) + ')</script>'

class OfficialMediaTests(unittest.TestCase):
    def test_official_discovery_is_available(self):
        self.assertTrue(callable(getattr(Sources(), 'official_images', None)))

    def test_real_album_structure_deduplicates_and_rejects_external_hosts(self):
        from publishing_v2.official_images import search_official
        def fetch(url, **kwargs):
            return (('<a href="/news/example/">EXOBOT launch</a>' if url.endswith('/news/') else page()).encode())
        rows = search_official('Ceer Motors', fetch=fetch)
        self.assertEqual(len(rows), 3)
        self.assertEqual({r['source_url'] for r in rows}, {ARTICLE})
        self.assertTrue(all(r['rights_status'] == 'permission_required' for r in rows))
        self.assertTrue(all(not image_publication_eligible(r) for r in rows))
        self.assertEqual(search_official('Unrelated brand', fetch=lambda *a, **k: self.fail('unexpected request')), [])

    def test_official_options_are_saved_without_counting_as_publishable_images(self):
        candidate = {'resolved_subjects': [{'name': 'Ceer Motors'}]}
        class Source:
            def official_images(self, subject): return [{'asset_id': 'official:1', 'rights_status': 'permission_required'}]
            def subject_images(self, query, subject): return []
        self.assertEqual(Renderer(None, Source()).plan_visuals(candidate), [])
        self.assertEqual(candidate['visual_discovery'][0]['asset_id'], 'official:1')

    def test_ceer_aliases_share_one_discovery_cache(self):
        source = Sources()
        with patch('publishing_v2.official_images.search_official', return_value=[{'asset_id': 'same'}]) as discover:
            first = source.official_images('Ceer Motors')
            first[0]['asset_id'] = 'changed'
            self.assertEqual(source.official_images('Ceer Exobot'), [{'asset_id': 'same'}])
            self.assertEqual(discover.call_count, 1)

    def test_failed_official_request_preserves_other_recovery_routes(self):
        from publishing_v2.public_images import ImageSourceError
        source = Sources()
        with patch('publishing_v2.official_images.search_official', side_effect=ImageSourceError('timeout')):
            self.assertEqual(source.official_images('Ceer Motors'), [])
        self.assertEqual(source.image_diagnostics[-1]['stage'], 'official_media')


import test_v2_autopilot as fixtures

class OfficialPipelineTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    pipeline = fixtures.PipelineTests.pipeline
    render = fixtures.PipelineTests.render
    publish = fixtures.PipelineTests.publish

    def test_missing_clearance_is_recorded_before_paid_research(self):
        pipeline = self.pipeline()
        def render(*args): self.fail('must not render uncleared images')
        def plan(candidate):
            candidate['visual_discovery'] = [{'asset_id': 'official:1', 'rights_status': 'permission_required'}]
            return []
        render.plan_visuals = plan
        pipeline.render = render
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertNotIn('researcher', self.agent.calls)
        self.assertTrue(any(e.get('reason') == 'images_found_usage_clearance_required' for e in result['audit']))
        self.assertEqual(result['official_image_candidates'][0]['asset_id'], 'official:1')
