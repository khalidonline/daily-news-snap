import copy
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from publishing_v2.autopilot.credits import render_compact_attribution
from publishing_v2.publication import publication_indices, validate_public_attribution
from tests.test_v2_autopilot_credits import asset

class CompactCreditsTests(unittest.TestCase):
    def test_legacy_companion_is_bound_but_never_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[Path(tmp)/'story.jpg',Path(tmp)/'credits.jpg']
            Image.new('RGB',(1080,1920),'white').save(paths[0])
            source=Path(tmp)/'source.jpg';Image.new('RGB',(1080,1920),'green').save(source)
            p={'cards':[{'kind':'story','image':asset(credit='Balkan Photos')},{'kind':'credits'}]}
            render_compact_attribution(p,paths,source)
            self.assertEqual(publication_indices(p['cards']),[0])
            validate_public_attribution(p['cards'][0],paths[0].read_bytes())
            with self.assertRaisesRegex(ValueError,'companion_required'):
                publication_indices(p['cards'][:1])
            broken=copy.deepcopy(p['cards']);broken[-1]['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'companion_changed'):
                publication_indices(broken)
            broken=copy.deepcopy(p['cards']);broken[-1]['attribution_companion']['images']=[]
            with self.assertRaisesRegex(ValueError,'companion_mismatch'):
                publication_indices(broken)
            with self.assertRaisesRegex(ValueError,'media_changed'):
                validate_public_attribution(p['cards'][0],b'changed')

    def test_new_label_keeps_source_metadata_and_excludes_credits(self):
        from publishing_v2.autopilot.credits import render_public_attribution
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'card.jpg'
            Image.new('RGB',(1080,1920),'white').save(path)
            row=asset(credit='A Long Photographer Name')
            card={'kind':'story','image':copy.deepcopy(row)}
            render_public_attribution(card,path)
            self.assertEqual(card['image'],row)
            self.assertEqual(card['public_attribution']['display_label'],'Wikimedia Commons')
            self.assertEqual(publication_indices([card,{'kind':'credits'}]),[0])
            self.assertEqual(publication_indices([card]),[0])
            card['public_attribution']['display_label']='Another Source'
            with self.assertRaisesRegex(ValueError,'label_changed'):
                validate_public_attribution(card)
