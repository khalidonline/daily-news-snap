import copy
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from publishing_v2.autopilot.credits import render_compact_attribution
from publishing_v2.publication import publication_indices, validate_public_attribution
from tests.test_v2_autopilot_credits import asset

class CompactCreditsTests(unittest.TestCase):
    def test_companion_is_required_bound_and_published_last(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[Path(tmp)/'story.jpg',Path(tmp)/'credits.jpg']
            Image.new('RGB',(1080,1920),'white').save(paths[0])
            source=Path(tmp)/'source.jpg';Image.new('RGB',(1080,1920),'green').save(source)
            p={'cards':[{'kind':'story','image':asset(credit='Balkan Photos')},{'kind':'credits'}]}
            render_compact_attribution(p,paths,source)
            self.assertEqual(publication_indices(p['cards']),[0,1])
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
