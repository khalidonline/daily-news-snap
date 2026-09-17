import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image

from publishing_v2.autopilot.runtime import Renderer, rollout_ready, publish_package, shadow_record


class RuntimeTests(unittest.TestCase):
    def test_existing_shadow_cannot_be_restamped_as_new_engine(self):
        result = {'engine': 'old', 'status': 'shadow_passed', 'started_at': '2026-09-17T00:00:00+00:00', 'approval': {}}
        with self.assertRaises(ValueError): shadow_record(result, 'new', 'slot')
    def test_rollout_requires_both_recent_shadow_lanes_and_same_code(self):
        now = datetime(2026, 9, 17, tzinfo=timezone.utc)
        entry = {'status': 'shadow_passed', 'engine': 'abc', 'at': now.isoformat()}
        self.assertFalse(rollout_ready({'daily': entry}, 'abc', now))
        self.assertTrue(rollout_ready({'daily': entry, 'local': entry}, 'abc', now))
        self.assertFalse(rollout_ready({'daily': entry, 'local': entry}, 'changed', now))

    def test_subject_alternatives_are_available_even_when_specific_results_exist(self):
        class Sources:
            def images(self, query):
                return ([{'asset_id': 'wrong', 'title': 'Coconut'}] if query == 'dates fruit varieties'
                        else [{'asset_id': 'right', 'title': 'Date fruit'}, {'asset_id': 'wrong'}])
        rows = Renderer(None, Sources()).image_options({'image_query': 'dates fruit varieties'},
                {'candidate': {'title': 'Date palm', 'editorial': {'research_query': 'Date fruit'}}})
        self.assertEqual([r['asset_id'] for r in rows], ['wrong', 'right'])

    def test_cards_share_relevant_assets_found_by_other_card_queries(self):
        class Sources:
            def images(self, query):
                return [{'asset_id': query}]
        catalog = Renderer(None, Sources()).image_catalog({'cards': [
            {'image_query': 'date palm'}, {'image_query': 'dried dates'}]})
        self.assertEqual([r['asset_id'] for r in catalog], ['date palm', 'dried dates'])

    def test_known_low_resolution_images_are_excluded_before_selection(self):
        class Sources:
            def images(self, query):
                return [{'asset_id': 'tiny', 'width': 400, 'height': 400},
                        {'asset_id': 'large', 'width': 1600, 'height': 900}]
        rows = Renderer(None, Sources()).image_options({'image_query': 'Mocha port'}, {})
        self.assertEqual([r['asset_id'] for r in rows], ['large'])

    def test_render_uses_flexible_numbering_and_preserves_image_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / 'source.png'
            Image.new('RGB', (1200, 1200), '#809070').save(image_path)
            raw = image_path.read_bytes()
            meta = {'download_url': 'https://upload.wikimedia.org/test.png',
                    'license': 'CC0', 'sha256': hashlib.sha256(raw).hexdigest()}
            package = {'cards': [dict(kind=kind, title='عنوان', body='معلومة', punch='', image=meta.copy())
                                 for kind in ['info', 'story', 'story']]}
            def frame(path, kicker, counter, *args, **kwargs):
                counters.append(counter); Image.new('RGB', (1080, 1920)).save(path)
            def info(spec, source, output):
                brands.append(spec['brand']); Image.new('RGB', (1080, 1920)).save(output)
            counters, brands = [], []
            with patch('publishing_v2.autopilot.runtime.get_bytes', return_value=raw), \
                 patch('publishing_v2.autopilot.runtime.render_card', side_effect=info), \
                 patch.dict('sys.modules', {'story_bot': SimpleNamespace(render_frame=frame)}):
                result = Renderer(None, None)(package, Path(tmp) / 'render')
            self.assertEqual(len(result), 3)
            self.assertEqual(counters, ['1 من 2', '2 من 2'])
            self.assertEqual(brands, ['ملخص تنفيذي - معلومة'])
            self.assertEqual(package['cards'][0]['image']['sha256'], meta['sha256'])

    def test_receipt_identity_is_hash_bound_and_posted_requires_all_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i in range(3):
                p = Path(tmp) / f'{i}.jpg'; p.write_bytes(str(i).encode()); paths.append(p)
            class Journal:
                def __init__(self): self.state = {}
                def read(self): return self.state
                def save(self, value): self.state = copy.deepcopy(value)
            class Client:
                def check(self): pass
                def upload(self, media): return 'upload'
                def create(self, title, upload): return title
                def wait(self, id): pass
            journal = Journal()
            result = publish_package({'title': 'test', 'expires_at': '2999-01-01T00:00:00+00:00'}, paths,
                                     client=Client(), journal_factory=lambda id: journal)
            self.assertEqual(result['status'], 'POSTED')
            self.assertEqual(len(result['post_ids']), 3)


if __name__ == '__main__': unittest.main()
