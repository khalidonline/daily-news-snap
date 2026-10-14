import copy, importlib.util, json, pathlib, unittest
BASE=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('archive_batch',BASE/'save_batch.py')
batch=importlib.util.module_from_spec(spec);spec.loader.exec_module(batch)
fixture=json.loads((BASE/'review-fixture.json').read_text())
class ArchiveBatchTests(unittest.TestCase):
    def setUp(self):
        self.a=json.loads((BASE/'nvidia-sega-20261007.json').read_text())
        self.r=copy.deepcopy(fixture['receipts']);self.b=copy.deepcopy(fixture['backlog'])
    def test_final_nvidia_order_and_media(self):
        result=batch.prepare(self.a,self.r,self.b)
        self.assertIsNotNone(result)
        self.assertEqual([r['post_id'] for r in result[2]],['4017285a-1b22-448b-9478-7919c7474dae','8362fe14-13cf-47dc-b563-ce2032db8bd3'])
    def test_all_five_current_approvals(self):
        for p in BASE.glob('*20261007.json'):
            a=json.loads(p.read_text());result=batch.prepare(a,self.r,self.b)
            self.assertIsNotNone(result)
            self.assertEqual(result[0],a['identity'])
    def test_reversed_sources_rejected(self):
        self.a['sources'].reverse()
        with self.assertRaises(ValueError): batch.prepare(self.a,self.r,self.b)
    def test_nonposted_source_rejected(self):
        self.r[self.a['sources'][0]['receipt_key']]['1']['status']='SENDING'
        with self.assertRaises(ValueError): batch.prepare(self.a,self.r,self.b)
    def test_wrong_reorder_authorization_rejected(self):
        self.r[self.a['sources'][1]['receipt_key']]['authorization']['content_identity']='0'*64
        with self.assertRaises(ValueError): batch.prepare(self.a,self.r,self.b)
    def test_wrong_reorder_predecessor_rejected(self):
        self.r[self.a['sources'][1]['receipt_key']]['1']['ordered_after_post_id']='older'
        with self.assertRaises(ValueError): batch.prepare(self.a,self.r,self.b)
    def test_changed_manifest_rejected(self):
        self.a['sources'][0]['manifest_sha256']='0'*64
        with self.assertRaises(ValueError): batch.prepare(self.a,self.r,self.b)
    def test_expired_approval_rejected(self):
        self.a['expires_at']='2020-01-01T00:00:00Z'
        with self.assertRaises(ValueError): batch.prepare(self.a,self.r,self.b)
    def test_unapproved_rejected(self):
        self.a['approved']=False
        with self.assertRaises(ValueError): batch.prepare(self.a,self.r,self.b)
    def test_superseded_package_rejected(self):
        next(b for b in self.b if b['identity']==self.a['source_backlog_identity'])['status']='SUPERSEDED'
        with self.assertRaises(ValueError): batch.prepare(self.a,self.r,self.b)
    def test_changed_final_lineage_rejected(self):
        next(b for b in self.b if b['identity']==self.a['source_backlog_identity'])['delivery_card_sources'][1]['receipt_key']='older'
        with self.assertRaises(ValueError): batch.prepare(self.a,self.r,self.b)
if __name__=='__main__': unittest.main()
