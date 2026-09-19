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

from publishing_v2.autopilot.runtime import Renderer, rollout_ready, publish_package, shadow_record, promotable_shadow


class RuntimeTests(unittest.TestCase):
    def test_repair_retains_selected_images_but_not_other_candidates(self):
        class Sources:
            def images(self, query):
                return [{'asset_id': query, 'title': query}]
        class Agent:
            def run(self, role, data):
                return {'image_ids': ['dates', None], 'reason': 'second image unavailable'}
        renderer = Renderer(Agent(), Sources())
        first = {'candidate': {'id': 'palm'}, 'cards': [
            {'image_query': 'dates'}, {'image_query': 'history'}]}
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, 'unknown_visual_selection'):
                renderer(first, root)
        repaired = {'candidate': {'id': 'palm'}, 'cards': [{'image_query': 'new query'}]}
        self.assertIn('dates', [r['asset_id'] for r in renderer.image_catalog(repaired)])
        repaired['repair'] = {'excluded_image_ids': ['dates']}
        self.assertNotIn('dates', [r['asset_id'] for r in renderer.image_catalog(repaired)])
        other = {'candidate': {'id': 'coffee'}, 'cards': [{'image_query': 'coffee pot'}]}
        self.assertNotIn('dates', [r['asset_id'] for r in renderer.image_catalog(other)])

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

    def test_promotion_preserves_reviewed_package_and_rejects_changed_or_old_state(self):
        from publishing_v2.autopilot.policy import digest, REVIEW_CHECKS
        now=datetime(2026,9,18,9,tzinfo=timezone.utc)
        package={'cards':[{}, {}, {}], 'expires_at':'2026-09-19T00:00:00+03:00'}
        state={'status':'shadow_passed','mode':'shadow','engine':'engine','lane':'daily',
               'started_at':now.isoformat(),'package':package,'audit':[],
               'approval':{'package_sha256':digest(package),'media_sha256':['a','b','c']},
               'review':{'checks':{k:True for k in REVIEW_CHECKS},'reason':'approved',
                         'card_checks':[{'readable':True,'relevant':True} for _ in range(3)]}}
        promoted=promotable_shadow(state,'engine','daily',now,'shadow-slot')
        self.assertEqual(promoted['status'],'approved')
        self.assertEqual(promoted['mode'],'live')
        self.assertEqual(promoted['approval'],state['approval'])
        self.assertEqual(promoted['package'],state['package'])
        self.assertEqual(state['mode'],'shadow')
        self.assertIsNone(promotable_shadow(state,'different','daily',now,'slot'))
        changed=copy.deepcopy(state); changed['package']['cards'][0]['body']='changed'
        self.assertIsNone(promotable_shadow(changed,'engine','daily',now,'slot'))
        state['started_at']='2026-09-17T00:00:00+00:00'
        self.assertIsNone(promotable_shadow(state,'engine','daily',now,'slot'))

    def test_render_uses_flexible_numbering_and_preserves_image_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / 'source.png'
            Image.new('RGB', (1200, 1200), '#809070').save(image_path)
            raw = image_path.read_bytes()
            meta = {'download_url': 'https://upload.wikimedia.org/test.png',
                    'license': 'CC0', 'sha256': hashlib.sha256(raw).hexdigest()}
            package = {'sources': [{'url': 'https://en.wikipedia.org/wiki/Coffee'}], 'cards': [dict(kind=kind, title='عنوان', body='معلومة', punch='', image=meta.copy())
                                 for kind in ['info', 'story', 'story']]}
            def frame(path, kicker, counter, *args, **kwargs):
                counters.append(counter); footers.append(kwargs.get('footer')); Image.new('RGB', (1080, 1920)).save(path)
            def info(spec, source, output):
                brands.append(spec['brand']); Image.new('RGB', (1080, 1920)).save(output)
            counters, brands, footers = [], [], []
            with patch('publishing_v2.autopilot.runtime.get_bytes', return_value=raw), \
                 patch('publishing_v2.autopilot.runtime.render_card', side_effect=info), \
                 patch.dict('sys.modules', {'story_bot': SimpleNamespace(render_frame=frame)}):
                result = Renderer(None, None)(package, Path(tmp) / 'render')
            self.assertEqual(len(result), 3)
            self.assertEqual(counters, ['1 من 2', '2 من 2'])
            self.assertEqual(footers, [None, 'المصادر: ويكيبيديا'])
            self.assertEqual(brands, ['ملخص تنفيذي - معلومة'])
            self.assertEqual(package['cards'][0]['image']['sha256'], meta['sha256'])

    def test_attributed_images_add_one_deterministic_reviewed_final_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            from publishing_v2.autopilot.policy import seal
            source = Path(tmp) / 'input.png'
            Image.new('RGB', (1600,1200), 'green').save(source)
            raw = source.read_bytes()
            meta = {'asset_id': '123', 'license': 'CC BY 4.0', 'credit': 'Photographer',
                    'title': 'File:Classroom.jpg', 'credit_line': 'Own work',
                    'license_url': 'https://creativecommons.org/licenses/by/4.0/',
                    'source_url': 'https://commons.wikimedia.org/wiki/File:Classroom.jpg',
                    'download_url': 'https://upload.wikimedia.org/classroom.jpg'}
            package = {'sources': [], 'cards': [dict(kind=kind,title='عنوان',body='معلومة',punch='',image=meta.copy())
                         for kind in ['info','story','story']]}
            def frame(path, *args, **kwargs): Image.new('RGB', (1080,1920)).save(path)
            def info(spec, source, output): Image.new('RGB', (1080,1920)).save(output)
            with patch('publishing_v2.autopilot.runtime.get_bytes', return_value=raw), \
                 patch('publishing_v2.autopilot.runtime.render_card', side_effect=info), \
                 patch.dict('sys.modules', {'story_bot': SimpleNamespace(render_frame=frame)}):
                renderer = Renderer(None,None)
                paths = renderer(package,Path(tmp)/'first')
                approved = seal(package,paths)
                resumed = renderer(package,Path(tmp)/'resume')
            self.assertEqual(len(paths),4)
            self.assertEqual(package['cards'][-1]['kind'],'credits')
            self.assertEqual(len(package['cards']),4)
            self.assertEqual(approved,seal(package,resumed))

    def test_attributed_package_uploads_only_verified_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i in range(3):
                path = Path(tmp)/f'review-{i}.png'; path.write_bytes(str(i).encode()); paths.append(path)
            video = Path(tmp)/'story.mp4'; video.write_bytes(b'verified complete video including credits')
            package = {'title': 'test', 'expires_at': '2999-01-01T00:00:00+00:00',
                       'cards': [{'kind':'info','image':{'license':'CC BY 4.0'}},{'kind':'story'},{'kind':'credits'}]}
            class Client:
                def __init__(self): self.uploads=[]; self.creates=0
                def check(self): pass
                def upload(self,item): self.uploads.append(item); return 'upload'
                def create(self,title,upload): self.creates+=1; return 'post'
                def wait(self,ident): pass
            class Journal:
                def __init__(self): self.state={}
                def read(self): return copy.deepcopy(self.state)
                def save(self,state): self.state=copy.deepcopy(state)
            client=Client(); journal=Journal()
            with self.assertRaisesRegex(ValueError,'attribution_requires_single_video_delivery'):
                publish_package(package,paths,client=client,journal_factory=lambda ident:journal)
            self.assertEqual(client.uploads,[])
            package['delivery']={'kind':'video','filename':'story.mp4','duration_seconds':35,
                'sha256':hashlib.sha256(video.read_bytes()).hexdigest(),
                'frame_sha256':[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]}
            receipt=publish_package(package,paths,client=client,journal_factory=lambda ident:journal)
            self.assertEqual(client.creates,1)
            self.assertEqual([item[0].suffix for item in client.uploads],['.mp4'])
            self.assertEqual(receipt['post_ids'],['post'])
            self.assertEqual(receipt['card_count'],3)
            video.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'approved_video_changed'):
                publish_package(package,paths,client=client,journal_factory=lambda ident:journal)
            self.assertEqual(client.creates,1)

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
