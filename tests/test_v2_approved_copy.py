import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from publishing_v2 import approved_copy as api

class ApprovedCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'photo.jpg').write_bytes(b'photo')
        self.cards = [dict(kind=k,title='عنوان',body='نص خالد\nبدون تغيير',punch='',photo='photo.jpg') for k in ('info','story','story')]
        self.doc = dict(version=1,cards=self.cards,approval={'reference':'Khalid approved exact test copy','copy_sha256':api.copy_hash(self.cards)})
        self.calls = []
    def renderer(self, card, photo, target, counter):
        self.calls.append(counter)
        target.write_text(json.dumps([card,counter],ensure_ascii=False))
    def run_render(self):
        return api.prepare(self.doc,self.root,self.root/'out',renderer=self.renderer)
    def test_entrypoint_exists(self):
        self.assertTrue(callable(getattr(api,'prepare',None)))
    def test_exact_text_and_arabic_counters_are_preserved(self):
        report=self.run_render()
        self.assertEqual(self.calls,['','١ من ٢','٢ من ٢'])
        self.assertEqual(json.loads((self.root/'out/card-00.jpg').read_text())[0]['body'],'نص خالد\nبدون تغيير')
        self.assertFalse(report['production_ready'])
    def test_replay_skips_and_edit_renders_only_affected_card(self):
        self.run_render(); self.calls.clear(); self.run_render()
        self.assertEqual(self.calls,[])
        self.cards[1]['body']='تعديل معتمد'
        self.doc['approval']['copy_sha256']=api.copy_hash(self.cards)
        report=self.run_render()
        self.assertEqual(report['rendered'],['card-01.jpg'])
        self.assertEqual(self.calls,['١ من ٢'])
    def test_changed_copy_rejected_before_render(self):
        self.cards[1]['body']='تعديل غير معتمد'
        with self.assertRaisesRegex(ValueError,'approval'): self.run_render()
        self.assertEqual(self.calls,[])
    def test_changed_photo_rebuilds_and_corrupt_output_is_not_reused(self):
        self.run_render();self.calls.clear()
        (self.root/'out/card-01.jpg').write_bytes(b'corrupt')
        self.assertEqual(self.run_render()['rendered'],['card-01.jpg'])
        (self.root/'photo.jpg').write_bytes(b'new photo')
        self.assertEqual(len(self.run_render()['rendered']),3)
    def test_unsafe_photo_rejected_before_any_render(self):
        self.cards[2]['photo']='../outside.jpg'
        self.doc['approval']['copy_sha256']=api.copy_hash(self.cards)
        with self.assertRaises(ValueError): self.run_render()
        self.assertEqual(self.calls,[])
