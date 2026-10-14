import copy,hashlib,tempfile,unittest
from pathlib import Path
import archive_batch as a
class Validation(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);p=Path(self.t.name)/'card.jpg';p.write_bytes(b'approved bytes');self.p=p
  self.item={'approved':True,'account':'executivesaudi','scope':'SAVED_STORY_ONLY','authorization':'Owner 2026-10-01 prepare final versions and save, excluding National Day','expires_at':'2099-01-01T00:00:00Z','package':'test','title':'test','source_identity':'a'*64,'source_rows':[{'status':'POSTED','post_id':'p','upload_id':'u'}],'media':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'kind':'story'}]}
  self.item['identity']=a.identity(self.item['media'])
 def test_approved_revision_valid(self):self.assertEqual(len(a.validate(self.item)),1)
 def test_changed_bytes_rejected(self):self.p.write_bytes(b'changed');self.assertRaises(ValueError,a.validate,self.item)
 def test_unapproved_rejected(self):self.item['approved']=False;self.assertRaises(ValueError,a.validate,self.item)
 def test_daily_scope_rejected(self):self.item['scope']='STORY';self.assertRaises(ValueError,a.validate,self.item)
 def test_national_day_excluded(self):self.item['package']='national-day-96-20260923';self.assertRaises(ValueError,a.validate,self.item)
 def test_source_incomplete_rejected(self):self.item['source_rows'][0]['status']='SENDING';self.assertRaises(ValueError,a.validate,self.item)
 def test_source_card_rejected(self):self.item['media'][0]['kind']='credits';self.assertRaises(ValueError,a.validate,self.item)
 def test_expired_rejected(self):self.item['expires_at']='2020-01-01T00:00:00Z';self.assertRaises(ValueError,a.validate,self.item)
 def test_wrong_identity_rejected(self):self.item['identity']='b'*64;self.assertRaises(ValueError,a.validate,self.item)
 def test_duplicate_card_rejected(self):self.item['media']*=2;self.item['identity']=a.identity(self.item['media']);self.assertRaises(ValueError,a.validate,self.item)
if __name__=='__main__':unittest.main()

class UploadTests(unittest.TestCase):
 def test_ambiguous_upload_never_retried(self):
  class J:
   state={}
   def read(self):return copy.deepcopy(self.state)
   def save(self,x):self.state=copy.deepcopy(x)
  class C:
   calls=0
   def upload(self,m):self.calls+=1;raise a.BundleError('timeout')
  c,j=C(),J()
  for _ in range(2):
   with self.assertRaises(a.BundleError):a.upload_once(c,j,'edition',0,(Path('a.jpg'),b'a'))
  self.assertEqual(c.calls,1)
 def test_upload_reused_after_restart(self):
  class J:
   state={}
   def read(self):return copy.deepcopy(self.state)
   def save(self,x):self.state=copy.deepcopy(x)
  class C:
   calls=0
   def upload(self,m):self.calls+=1;return 'upload'
  c,j=C(),J()
  for _ in range(2):self.assertEqual(a.upload_once(c,j,'edition',0,(Path('a.jpg'),b'a')),'upload')
  self.assertEqual(c.calls,1)
