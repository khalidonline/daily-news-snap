import copy, tempfile, unittest
from pathlib import Path
from importlib.util import find_spec

class CacheTests(unittest.TestCase):
    def test_only_changed_image_is_sent_again(self):
        self.assertIsNotNone(find_spec('publishing_v2.image_review_cache'))
        from publishing_v2.image_review_cache import ImageReviewCache
        states={}
        class Store:
            def __init__(self,key): self.key=key
            def read(self): return copy.deepcopy(states.get(self.key,{}))
            def save(self,row): states[self.key]=copy.deepcopy(row)
        calls=[]
        def review(data,images):
            ids=[x['asset_id'] for x in data['options']]; calls.append(ids)
            return {'accepted_ids':ids,'descriptions':{},'reason':'ok'}
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a',Path(folder)/'b'; a.write_bytes(b'a'); b.write_bytes(b'b')
            data={'subject':'Mac','source_title':'desktop','options':[{'asset_id':'a'},{'asset_id':'b'}]}
            c=ImageReviewCache(Store,'prompt/model-v1')
            c.run(data,[a,b],review)
            ImageReviewCache(Store,'prompt/model-v1').run(data,[a,b],review)
            self.assertEqual(calls,[['a','b']])
            b.write_bytes(b'changed'); c.run(data,[a,b],review)
            self.assertEqual(calls[-1],['b'])
            c.run(dict(data,subject='another subject'),[a,b],review)
            self.assertEqual(calls[-1],['a','b'])
            ImageReviewCache(Store,'new model').run(data,[a,b],review)
            self.assertEqual(calls[-1],['a','b'])

if __name__=='__main__': unittest.main()
