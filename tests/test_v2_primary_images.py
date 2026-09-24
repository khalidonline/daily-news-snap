import json
import unittest
from unittest.mock import patch
from publishing_v2 import primary_images as primary

class PrimaryImagesTests(unittest.TestCase):
    def test_article_uses_declared_images_not_navigation_or_ads(self):
        html='<meta property="og:image" content="https://cdn.example/car.jpg"><img src="/ad.jpg">'
        html+='<script type="application/ld+json">'+json.dumps({'@type':'NewsArticle','image':[{'url':'https://cdn.example/interior.jpg','caption':'Interior'}]})+'</script>'
        rows=primary.page_images(html,'https://aawsat.com/node/123','سير',kind='article')
        self.assertEqual(len(rows),2)
        self.assertTrue(all(primary.owner_primary_use(row) for row in rows))
        self.assertTrue(all(row['licensing_verified'] is False for row in rows))
        self.assertNotIn('ad.jpg',str(rows))

    def test_source_identity_cannot_be_swapped(self):
        row=primary.page_images('<meta property="og:image" content="https://cdn.example/car.jpg">',
             'https://aawsat.com/node/123','Ceer',kind='article')[0]
        for changes in [{'source_url':'https://other.example/article'}, {'download_url':'https://cdn.example/other.jpg'},
                        {'owner_use_decision':'invented'}]:
            self.assertFalse(primary.owner_primary_use(dict(row,**changes)))

    def test_private_networks_and_credentials_are_blocked(self):
        for url in ['http://example.com/a','https://127.0.0.1/a','https://u:p@example.com/a','https://example.com:8443/a']:
            with self.subTest(url=url),self.assertRaises(ValueError):
                primary.public_url(url)
        with patch.object(primary.socket,'getaddrinfo',return_value=[(2,1,6,'',('10.0.0.1',443))]):
            with self.assertRaises(ValueError):primary.public_url('https://cdn.example/a')

    def test_memory_is_scoped_and_expiring(self):
        class Store:
            data={}
            def read(self):return self.data
            def save(self,data):self.data=data
        store=Store(); memory=primary.ImageMemory(store,clock=lambda:100)
        row={'asset_id':'street','original_url':'https://cdn.example/street.jpg','provider':'commons'}
        memory.record('BlackRock',row,False);memory.save()
        self.assertTrue(primary.ImageMemory(store,clock=lambda:101).rejected('BlackRock',row))
        self.assertFalse(memory.rejected('Blackrock street',row))
        self.assertFalse(primary.ImageMemory(store,clock=lambda:100+8*86400).rejected('BlackRock',row))

    def test_info_story_reuse_allowed_but_story_reuse_rejected(self):
        from publishing_v2.autopilot.policy import validate_image_variety
        image={'asset_id':'portrait','origin_key':'one-photo'}
        info={'kind':'info','image':image}
        story={'kind':'story','image':image}
        validate_image_variety([info,story,{'kind':'credits','image':image}])
        with self.assertRaisesRegex(ValueError,'duplicate_story_image'):
            validate_image_variety([story,story])
        with self.assertRaisesRegex(ValueError,'duplicate_source_image'):
            validate_image_variety([info,story,story])

    def test_article_pool_precedes_general_search(self):
        from publishing_v2.autopilot.sources import Sources
        source=Sources(recovery=True)
        source.primary_pools['Ceer']=primary.page_images(
            '<script type="application/ld+json">{"@type":"NewsArticle","image":["https://cdn.example/a.jpg","https://cdn.example/b.jpg"]}</script>',
            'https://aawsat.com/node/123','Ceer',kind='article')
        with patch.object(source,'official_images',return_value=[]), \
             patch('publishing_v2.autopilot.sources.download_image',side_effect=[b'a',b'b']), \
             patch('publishing_v2.autopilot.sources.search_commons') as stock:
            rows=source.subject_images('Ceer','Ceer')
        self.assertEqual(len(rows),2)
        stock.assert_not_called()

    def test_official_site_comes_from_resolved_entity(self):
        from publishing_v2.autopilot.sources import Sources
        source=Sources();source.subject_entities['BlackRock']='Q219635'
        data={'claims':{'P856':[{'mainsnak':{'datavalue':{'value':'https://www.blackrock.com/'}}}]}}
        with patch('publishing_v2.autopilot.sources.wiki_json',return_value=data) as wiki, \
             patch('publishing_v2.autopilot.sources.official_site_images',return_value=[]) as official:
            source.prime_images({'url':'https://aawsat.com/node/123'},'BlackRock')
        self.assertIn('entity=Q219635',wiki.call_args.args[0])
        official.assert_called_once_with('https://www.blackrock.com/','Q219635','BlackRock')

    def test_early_pixel_rejection_is_remembered_before_writing(self):
        from publishing_v2.autopilot.sources import Sources
        from publishing_v2.autopilot.runtime import Renderer
        source=Sources();source.image_bytes={'street':b'pixels','building':b'pixels2'}
        rows=[{'asset_id':v,'title':v,'original_url':'https://cdn.example/'+v,'provider':'commons'} for v in ['street','building']]
        class Agent:
            def run(self,role,data,images=()):
                self.role=role
                assert len(images)==2
                assert images[0].read_bytes()==b'pixels'
                return {'accepted_ids':['building'],'descriptions':{'building':'Glass building exterior','street':'Wrong subject'},'reason':'Street is unrelated'}
        agent=Agent();result=Renderer(agent,source).check_source_images({'title':'Company news'},'BlackRock',rows)
        self.assertEqual(agent.role,'image_check')
        self.assertEqual([r['asset_id'] for r in result],['building'])
        self.assertEqual(result[0]['pixel_description'],'Glass building exterior')
        self.assertNotIn('pixel_description',rows[0])
        self.assertTrue(source.image_memory.rejected('BlackRock',rows[0]))
        self.assertFalse(source.image_memory.rejected('BlackRock',rows[1]))

    def test_article_figure_images_keep_caption_and_ignore_navigation(self):
        rows=primary.page_images('<img src="/navigation.jpg"><article><figure><img src="/plant.jpg" alt="Factory exterior"></figure></article>',
             'https://aawsat.com/node/123','Company',kind='article')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['title'],'Factory exterior')

    def test_nasa_owner_use_keeps_original_rights_status(self):
        row={'provider':'nasa','asset_id':'equator','source_url':'https://images.nasa.gov/details/equator',
             'original_url':'https://images-assets.nasa.gov/image/equator/photo.jpg',
             'download_url':'https://images-assets.nasa.gov/image/equator/photo.jpg',
             'license':'review_required','licensing_verified':False,
             'owner_use_decision':primary.OWNER_DECISION,'rights_status':'owner_accepted_editorial_use'}
        self.assertTrue(primary.owner_primary_use(row))
        self.assertFalse(primary.owner_primary_use(dict(row,source_url='https://other.example/equator')))
        self.assertEqual(row['license'],'review_required')

    def test_pixel_preflight_uses_small_budgeted_vision_request(self):
        import tempfile
        from pathlib import Path
        from PIL import Image
        from test_v2_autopilot_recovery import FormatRecoveryTests
        agent,ledger,calls=FormatRecoveryTests().agent(['{"accepted_ids":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'photo.jpg';Image.new('RGB',(1200,800)).save(path)
            agent.run('image_check',{'subject':'Company','options':[]},images=[path])
        self.assertEqual(calls[0]['max_tokens'],2048)
        self.assertEqual(calls[0]['model'],'claude-sonnet-5')
        self.assertEqual(len(ledger.reserved),1)
        self.assertEqual(calls[0]['messages'][0]['content'][0]['type'],'image')
