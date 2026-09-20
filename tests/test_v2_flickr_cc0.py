import json
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
from publishing_v2 import flickr_images as flickr
from publishing_v2.public_images import ImageSourceError
from publishing_v2.publication import image_without_public_credit

URL='https://www.flickr.com/photos/alice/123/'
CC0='https://creativecommons.org/publicdomain/zero/1.0/'
BY='https://creativecommons.org/licenses/by/2.0/'

def page(license_id=9, license_url=CC0):
    row={'id':'123','license':license_id,'safetyLevel':0,'title':'Jeddah harbor',
         'description':'Jeddah waterfront','sizes':{'data':{'l':{'data':{
         'url':'//live.staticflickr.com/1/123_abc_b.jpg','width':1600,'height':1100}}}}}
    model={'main':{'photo-models':[{'data':row}]}}
    record={'@type':'ImageObject','license':license_url,'acquireLicensePage':URL,
            'author':{'name':'Alice'}}
    return ('<script>modelExport: '+json.dumps(model)+'</script><script type="application/ld+json">'+json.dumps(record)+'</script>').encode()

class FlickrCC0Tests(unittest.TestCase):
    def test_verified_cc0_is_public_eligible(self):
        with patch.object(flickr,'get_bytes',return_value=page()):
            row=flickr.photo(URL, publication_only=True)
        self.assertTrue(image_without_public_credit(row))
        self.assertEqual(row['license_url'],CC0)
        self.assertTrue(row['source_verified'])

    def test_page_model_and_license_must_agree(self):
        for identity,license_url in [(9,BY),(4,CC0),(4,BY),(0,CC0),(10,CC0)]:
            with self.subTest(identity=identity,url=license_url), \
                 patch.object(flickr,'get_bytes',return_value=page(identity,license_url)), \
                 self.assertRaises(ImageSourceError):
                flickr.photo(URL, publication_only=True)

    def test_public_search_filters_and_rechecks_actual_photo_page(self):
        search={'main':{'search-photos-lite-models':[{'data':{'photos':{'data':{'_data':[
            {'data':{'id':'123','pathAlias':'alice','title':'Jeddah harbor'}}]}}}}]}}
        def fetch(url,**kwargs):
            if url.startswith('https://www.flickr.com/search/'):
                self.assertEqual(parse_qs(urlsplit(url).query)['license'],['9'])
                return ('<script>modelExport: '+json.dumps(search)+'</script>').encode()
            self.assertEqual(url,URL)
            return page()
        with patch.object(flickr,'get_bytes',side_effect=fetch):
            rows=flickr.search_flickr('Jeddah',publication_only=True)
        self.assertEqual([r['asset_id'] for r in rows],['flickr:123'])
        self.assertTrue(image_without_public_credit(rows[0]))

    def test_default_review_mode_keeps_cc_by(self):
        with patch.object(flickr,'get_bytes',return_value=page(4,BY)):
            row=flickr.photo(URL)
        self.assertEqual(row['license'],'CC BY 2.0')
        self.assertFalse(image_without_public_credit(row))
