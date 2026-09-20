"""Public planning must not exhaust its pool on review-only attribution assets."""
import unittest
from unittest.mock import patch
from publishing_v2.autopilot.sources import Sources
from publishing_v2.autopilot.runtime import Renderer
from test_v2_autopilot_credits import asset


class PublicImagePoolTests(unittest.TestCase):
    def run_pool(self, recovery, publication_only, overflowing=True):
        source = Sources(recovery=recovery, publication_only=publication_only)
        credited = [dict(asset(asset_id=str(i)), title='Jeddah waterfront',
                         width=1600, height=1100, rights_links=('W'*400 if overflowing else '')) for i in range(5)]
        public = [dict(row, asset_id=str(10+i), license='CC0',
                       attribution_required='false') for i, row in enumerate(credited[:3])]
        def search(query, limit=5, offset=0):
            return public if offset else credited
        downloads = []
        def download(row):
            downloads.append(row['asset_id'])
            return row['asset_id'].encode()
        with patch('publishing_v2.autopilot.sources.search_commons', side_effect=search), \
             patch('publishing_v2.autopilot.sources.search_commons_category', return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_flickr', return_value=[]) as flickr, \
             patch('publishing_v2.autopilot.sources.download_image', side_effect=download):
            rows = source.subject_images('Jeddah', 'Jeddah')
            planned = Renderer(None, source).plan_visuals({'resolved_subjects':[{'name':'Jeddah'}]})
            if publication_only and recovery:
                self.assertTrue(any(call.kwargs['publication_only'] for call in flickr.call_args_list))
        return rows, planned, downloads

    def test_recovery_reaches_public_images_beyond_first_five_credited_images(self):
        rows, planned, downloads = self.run_pool(True, True)
        self.assertEqual([row['asset_id'] for row in planned], ['10', '11', '12'])
        self.assertEqual(downloads, ['10', '11', '12'])

    def test_non_recovery_search_also_keeps_looking_for_public_images(self):
        rows, planned, _ = self.run_pool(False, True)
        self.assertEqual([row['asset_id'] for row in planned], ['10', '11', '12'])

    def test_review_mode_preserves_attribution_assets(self):
        rows, _, _ = self.run_pool(True, False, overflowing=False)
        self.assertEqual([row['asset_id'] for row in rows], ['0', '1', '2', '3', '4'])
