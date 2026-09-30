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

class ArchiveTests(unittest.TestCase):
    def test_reviewed_legacy_and_credit_selection(self):
        import tempfile, os, json, hashlib
        from pathlib import Path
        from publishing_v2.saved_story_api import validate_archive
        cwd=os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            try:
                os.chdir(d)
                frames=[]
                for i,kind in enumerate([None,'story','credits']):
                    data=str(i).encode();Path(f'{i}.jpg').write_bytes(data)
                    f={'path':f'{i}.jpg','sha256':hashlib.sha256(data).hexdigest()}
                    if kind:f['kind']=kind
                    frames.append(f)
                raw=json.dumps({'approved':True,'account':'executivesaudi','title':'t','media':frames}).encode()
                Path('manifest.json').write_bytes(raw)
                identity=hashlib.sha256(('executivesaudi:'+':'.join(f['sha256'] for f in frames)).encode()).hexdigest()
                a={'approved':True,'account':'executivesaudi','empty_profile_confirmation':'owner baseline',
                   'expires_at':'2099-01-01T00:00:00Z','manifest':'manifest.json','manifest_sha256':hashlib.sha256(raw).hexdigest(),
                   'identity':identity,'public_indices':[1,2],'reviewed_public_sha256':[frames[0]['sha256']]}
                source={str(i):{'status':'POSTED','post_id':str(i),'upload_id':str(i)} for i in range(1,4)}
                self.assertEqual([r['upload_id'] for r in validate_archive(a,source)[2]],['1','2'])
                for changes in [{'public_indices':[1,2,3]},{'public_indices':[1]},{'public_indices':[2,1]},{'reviewed_public_sha256':[]}]:
                    with self.assertRaises(BundleError):validate_archive(dict(a,**changes),source)
            finally:os.chdir(cwd)
