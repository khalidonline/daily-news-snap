import io
import json
import unittest
from unittest.mock import patch
from PIL import Image
from publishing_v2 import public_images as images
from publishing_v2.autopilot.credits import attribution_eligible, _blocks
from test_v2_autopilot_credits import asset, package

class MultiSourceTests(unittest.TestCase):
    def test_flickr_verified_source_has_correct_credit_link_and_identity(self):
        row=asset(provider='flickr',asset_id='flickr:123',source_url='https://www.flickr.com/photos/alice/123/',
                  source_verified=True)
        self.assertTrue(attribution_eligible(row))
        text='\n'.join(t for t,b in _blocks(package([row,asset()])))
        self.assertIn(row['source_url'],text)
        self.assertIn('https://commons.wikimedia.org/?curid=123',text)
        self.assertFalse(attribution_eligible(dict(row,source_verified=False)))
        self.assertFalse(attribution_eligible(dict(row,source_url='https://www.flickr.com/photos/alice/456/')))

    def test_original_resolution_recovery_keeps_same_asset(self):
        self.assertTrue(hasattr(images, 'download_image'), 'original-file recovery is missing')
        buf=io.BytesIO();Image.new('RGB',(1600,1100)).save(buf,'JPEG');raw=buf.getvalue()
        row={'download_url':'https://upload.wikimedia.org/thumb.jpg','original_url':'https://upload.wikimedia.org/original.jpg'}
        with patch.object(images,'get_bytes',side_effect=[images.ImageSourceError('http_404'),raw]):
            found=images.download_image(row)
        self.assertEqual(found,raw)
        self.assertEqual(row['download_url'],row['original_url'])

    def test_flickr_download_hosts_are_exact(self):
        try:images.validate_url('https://live.staticflickr.com/1/123_abc_b.jpg')
        except images.ImageSourceError:self.fail('verified Flickr image host is not supported')
        for url in ['https://live.staticflickr.com.evil.test/a.jpg','https://user@live.staticflickr.com/a.jpg',
                    'https://live.staticflickr.com:999/a.jpg']:
            with self.assertRaises(images.ImageSourceError):images.validate_url(url)

    def test_recovery_uses_second_source_after_download_failure_and_keeps_metadata_only(self):
        from publishing_v2.autopilot.sources import Sources
        self.assertTrue(hasattr(Sources, 'recover_images'), 'multi-source recovery is missing')
        good=dict(asset(provider='flickr',asset_id='flickr:123',source_url='https://www.flickr.com/photos/alice/123/',source_verified=True),
                  title='Jeddah waterfront',download_url='https://live.staticflickr.com/1/123_ab.jpg',width=1600,height=1100)
        bad=dict(good,asset_id='flickr:456',source_url='https://www.flickr.com/photos/alice/456/',download_url='https://live.staticflickr.com/1/456_ab.jpg')
        source=Sources(recovery=True)
        buf=io.BytesIO();Image.new('RGB',(1600,1100)).save(buf,'JPEG');raw=buf.getvalue()
        with patch('publishing_v2.autopilot.sources.search_commons',return_value=[bad]), \
             patch('publishing_v2.autopilot.sources.search_commons_category',return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_flickr',return_value=[good]), \
             patch('publishing_v2.autopilot.sources.download_image',side_effect=[images.ImageSourceError('http_404'),raw]):
            result=source.subject_images('Jeddah','Jeddah')
            self.assertEqual([r['asset_id'] for r in result],['flickr:123'])
            self.assertEqual(source.subject_images('Jeddah','Jeddah'),result)
        self.assertTrue(result[0]['sha256'])
        self.assertFalse(any(isinstance(value,bytes) for value in result[0].values()))

    def test_source_files_are_temporary_even_on_render_failure(self):
        from publishing_v2.autopilot.runtime import Renderer
        from pathlib import Path
        import tempfile
        self.assertTrue(hasattr(Renderer, '_render'), 'temporary source rendering is missing')
        used=[]
        def fail(package,output,source_root):
            used.append(source_root);(source_root/'source-00.jpg').write_bytes(b'temporary')
            raise ValueError('render_failed')
        with tempfile.TemporaryDirectory() as tmp, patch.object(Renderer,'_render',side_effect=fail):
            with self.assertRaisesRegex(ValueError,'render_failed'):Renderer(None,None)({},Path(tmp))
        self.assertFalse(used[0].exists())

    def test_flickr_license_is_verified_on_actual_photo_page(self):
        from publishing_v2 import flickr_images
        row={'id':'123','license':4,'safetyLevel':0,'title':'Jeddah harbor','description':'Jeddah waterfront',
             'sizes':{'data':{'l':{'data':{'url':'//live.staticflickr.com/1/123_ab_b.jpg','width':1600,'height':1100}}}}}
        model={'main':{'photo-models':[{'data':row}]}}
        obj={'@type':'ImageObject','license':'https://creativecommons.org/licenses/by/2.0/',
             'acquireLicensePage':'https://www.flickr.com/photos/alice/123/', 'author':{'name':'Alice','url':'https://www.flickr.com/photos/alice'}}
        def html():return ('<script>modelExport: '+json.dumps(model)+'</script><script type="application/ld+json">'+json.dumps(obj)+'</script>').encode()
        with patch.object(flickr_images,'get_bytes',side_effect=lambda *a,**k:html()):
            photo=flickr_images.photo('https://www.flickr.com/photos/alice/123/')
            self.assertTrue(attribution_eligible(photo))
            self.assertEqual(photo['asset_id'],'flickr:123')
            obj['license']='https://creativecommons.org/licenses/by-nc/2.0/'
            with self.assertRaises(images.ImageSourceError):flickr_images.photo(photo['source_url'])

    def test_cross_provider_original_is_not_used_three_times(self):
        from publishing_v2.autopilot.policy import validate_image_variety
        cards=[{'image':{'asset_id':'123','origin_key':'flickr:456'}},
               {'image':{'asset_id':'flickr:456','origin_key':'flickr:456'}},
               {'image':{'asset_id':'another-copy','origin_key':'flickr:456'}}]
        with self.assertRaisesRegex(ValueError,'duplicate_source_image'):validate_image_variety(cards)

    def test_production_catalog_uses_download_verified_pool(self):
        from publishing_v2.autopilot.sources import Sources
        from publishing_v2.autopilot.runtime import Renderer
        source=Sources(recovery=True)
        good={'asset_id':'checked','title':'Jeddah waterfront','license':'CC0','width':1600,'height':1100}
        candidate={'resolved_subjects':[{'name':'Jeddah'}]}
        with patch.object(source,'subject_images',return_value=[good]), \
             patch.object(source,'images',return_value=[dict(good,asset_id='unchecked')]):
            rows=Renderer(None,source).image_options({'image_query':'Jeddah historic street'}, {'candidate':candidate})
        self.assertEqual(rows,[good])

    def test_known_small_original_does_not_consume_download_budget(self):
        from publishing_v2.autopilot.sources import Sources
        row={'provider':'commons','asset_id':'1','title':'Jeddah','license':'CC0',
             'width':500,'height':400,'original_width':500,'original_height':400}
        with patch('publishing_v2.autopilot.sources.search_commons',return_value=[row]), \
             patch('publishing_v2.autopilot.sources.search_commons_category',return_value=[]), \
             patch('publishing_v2.autopilot.sources.search_flickr',return_value=[]):
            source=Sources(recovery=True);source.subject_images('Jeddah','Jeddah')
        reasons=[d['rejections'] for d in source.image_diagnostics]
        self.assertTrue(any(d.get('original_too_small') for d in reasons))

    def test_distant_incidental_words_do_not_establish_subject(self):
        from publishing_v2.autopilot.sources import subject_metadata_matches
        self.assertFalse(subject_metadata_matches('Saudi coffee',{'title':'Swedish coffee shop',
            'description':'A chain founded in Stockholm with many branches across Scandinavia and Saudi Arabia.'}))
        self.assertTrue(subject_metadata_matches('Saudi coffee',{'title':'Traditional Saudi Arabian coffee'}))
        self.assertTrue(subject_metadata_matches('Diego Simeone',{'title':'Diego Pablo Simeone'}))
