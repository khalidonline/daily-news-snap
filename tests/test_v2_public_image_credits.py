import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from publishing_v2.autopilot.credits import render_public_attribution
from publishing_v2.publication import publication_indices, validate_public_attribution
from tests.test_v2_autopilot_credits import asset

class PublicCreditsTests(unittest.TestCase):
    def test_render_binds_complete_credit_to_pixels_and_excludes_private_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'card.jpg'
            Image.new('RGB',(1080,1920),'red').save(path)
            card={'kind':'info','image':asset()}
            render_public_attribution(card,path)
            self.assertEqual(publication_indices([card,{'kind':'credits'}]),[0])
            validate_public_attribution(card,path.read_bytes())
            with Image.open(path) as image:
                self.assertEqual(image.size,(1080,1920))
                self.assertGreater(len(image.crop((64,1840,1016,1900)).getcolors(952*60)),50)
            with self.assertRaisesRegex(ValueError,'public_attribution'):
                validate_public_attribution(card,b'changed pixels')
            card['image']['credit']='Different photographer'
            with self.assertRaisesRegex(ValueError,'public_attribution'):
                publication_indices([card])

    def test_unrendered_or_unsupported_credit_never_publishes(self):
        for row in [asset(),asset(license='CC BY-SA 4.0'),asset(credit='')]:
            with self.assertRaisesRegex(ValueError,'public_attribution'):
                publication_indices([{'kind':'info','image':row}])

    def test_overflow_does_not_write_partial_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'card.jpg';Image.new('RGB',(1080,1920),'red').save(path)
            before=path.read_bytes()
            card={'kind':'info','image':asset(title='W'*180,credit='W'*120,credit_line='W'*200,
                    rights_links='W'*400,copyright_notice='W'*400)}
            with self.assertRaisesRegex(ValueError,'public_attribution_layout_overflow'):
                render_public_attribution(card,path)
            self.assertEqual(path.read_bytes(),before)
            self.assertNotIn('public_attribution',card)

    def test_real_render_to_auto_and_manual_publication(self):
        import io
        import json
        from unittest.mock import patch
        from publishing_v2.autopilot.runtime import Renderer, publish_package
        from publishing_v2.bundle_api import load_package, BundleError
        from tests.test_v2_publication_selection import Client, Journal
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); raws=[]; cards=[]
            for i,color in enumerate(['red','green','blue']):
                buffer=io.BytesIO();Image.new('RGB',(1600,1200),color).save(buffer,'JPEG');raws.append(buffer.getvalue())
                cards.append({'kind':'info' if i==0 else 'story','title':'اختبار الصورة',
                    'body':'معلومة لاختبار وضوح النص وحقوق الصورة.','punch':'',
                    'image':asset(asset_id=str(i),download_url='https://upload.wikimedia.org/test.jpg')})
            package={'title':'Review only','expires_at':'2999-01-01T00:00:00+00:00','cards':cards,'sources':[]}
            with patch('publishing_v2.autopilot.runtime.get_bytes',side_effect=raws),patch.dict('os.environ',{'THEME':'light','FONT_FAMILY':'Almarai'}):
                paths=Renderer(None,None)(package,root)
            client=Client()
            publish_package(package,paths,client=client,journal_factory=lambda _:Journal())
            self.assertEqual(len(client.uploaded),3)
            self.assertNotIn(paths[-1].read_bytes(),client.uploaded)
            manifest={'approved':True,'account':'executivesaudi','title':'test','expires_at':package['expires_at'],
                'media':[dict(c,path=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                         for c,p in zip(package['cards'],paths)]}
            target=root/'manifest.json';target.write_text(json.dumps(manifest))
            with patch('pathlib.Path.cwd',return_value=root):
                self.assertEqual(len(load_package('manifest.json')[2]),3)
                duplicate=copy.deepcopy(manifest)
                duplicate['media'][1]['image']=copy.deepcopy(duplicate['media'][0]['image'])
                duplicate['media'][2]['image']=copy.deepcopy(duplicate['media'][0]['image'])
                target.write_text(json.dumps(duplicate))
                with self.assertRaisesRegex(BundleError,'duplicate'):
                    load_package('manifest.json')
                paths[0].write_bytes(b'tampered')
                manifest['media'][0]['sha256']=hashlib.sha256(b'tampered').hexdigest()
                target.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(BundleError,'public_attribution_media_changed'):
                    load_package('manifest.json')
            client=Client()
            with self.assertRaisesRegex(ValueError,'public_attribution_media_changed'):
                publish_package(package,paths,client=client)
            self.assertEqual(client.uploaded,[])

    def test_public_flickr_attribution_recovery(self):
        from unittest.mock import patch
        from publishing_v2.autopilot.sources import Sources
        from publishing_v2.autopilot.runtime import Renderer
        row=asset(provider='flickr',asset_id='flickr:123',source_verified=True,
                  source_url='https://www.flickr.com/photos/alice/123/',
                  title='Jeddah waterfront',width=1600,height=1100)
        with patch('publishing_v2.autopilot.sources.search_commons',return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_commons_category',return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_met',return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_flickr',side_effect=lambda *a,**k:[] if k['publication_only'] else [row]), \
             patch('publishing_v2.autopilot.sources.download_image',return_value=b'downloaded'):
            source=Sources(recovery=True,publication_only=True)
            renderer=Renderer(None,source)
            renderer.check_source_images=lambda candidate,subject,rows:rows
            planned=renderer.plan_visuals({'resolved_subjects':[{'name':'Jeddah'}]})
            self.assertEqual([r['asset_id'] for r in planned],['flickr:123'])
