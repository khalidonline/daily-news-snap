import copy
import unittest
from publishing_v2.saved_story_api import save_story, BundleError

class Journal:
    def __init__(self): self.state={}; self.fail=False
    def read(self): return copy.deepcopy(self.state)
    def save(self,s):
        if self.fail: raise BundleError('journal unavailable')
        self.state=copy.deepcopy(s)
class Client:
    def __init__(self): self.created=0; self.found=[]; self.timeout=False
    def find(self,*a): return self.found
    def ensure_capacity(self,n): assert n==1
    def create_saved(self,*a):
        self.created+=1
        if self.timeout: raise BundleError('timeout')
        return 'id1'
    def confirm(self,p,*a): return {'id':p,'status':'POSTED','externalData':{}}
class Tests(unittest.TestCase):
    def test_one_save_and_repeat(self):
        c,j=Client(),Journal(); save_story(c,j,'identity','title',['a','b']); save_story(c,j,'identity','title',['a','b'])
        self.assertEqual(c.created,1)
    def test_ambiguous_send_never_recreated(self):
        c,j=Client(),Journal(); c.timeout=True
        with self.assertRaises(BundleError): save_story(c,j,'identity','title',['a'])
        c.timeout=False
        with self.assertRaises(BundleError): save_story(c,j,'identity','title',['a'])
        self.assertEqual(c.created,1)
    def test_reconcile_ambiguous(self):
        c,j=Client(),Journal();j.state={'status':'SENDING','identity':'identity','upload_ids':['a']};c.found=['existing']
        save_story(c,j,'identity','title',['a']);self.assertEqual(c.created,0);self.assertEqual(j.state['post_id'],'existing')
    def test_journal_failure_prevents_request(self):
        c,j=Client(),Journal();j.fail=True
        with self.assertRaises(BundleError):save_story(c,j,'identity','title',['a'])
        self.assertEqual(c.created,0)
    def test_existing_provider_story_not_duplicated(self):
        c,j=Client(),Journal();c.found=['old']
        save_story(c,j,'identity','title',['a']);self.assertEqual(c.created,0)
    def test_multiple_matches_block(self):
        c,j=Client(),Journal();c.found=['one','two']
        with self.assertRaises(BundleError):save_story(c,j,'identity','title',['a'])
        self.assertEqual(c.created,0)
    def test_changed_media_blocks_resume(self):
        c,j=Client(),Journal();j.state={'identity':'identity','upload_ids':['different']}
        with self.assertRaises(BundleError):save_story(c,j,'identity','title',['a'])
if __name__=='__main__':unittest.main()
