import copy
import json
import pytest
from publishing_v2 import bundle_api as b

ERROR=json.dumps({'statusCode':400,'issues':[{'code':'custom','message':'Max 1 upload(s) allowed','path':['data','SNAPCHAT','uploadIds']}]})
class Journal:
    def __init__(self):
        self.state={'_group':{'identity':'identity','uploads':['u1','u2'],'reference_key':'story-identity','status':'SENDING','draft_validation':{'status':'REJECTED','http_status':400,'error':ERROR}},'1':{'status':'SENDING','upload_id':'u1'},'2':{'status':'SENDING','upload_id':'u2'}}
        self.fail=False
    def read(self): return copy.deepcopy(self.state)
    def save(self,s):
        if self.fail: raise b.BundleError('journal unavailable')
        self.state=copy.deepcopy(s)
class Client(b.BundleClient):
    team='team'
    def __init__(self): self.posts=[];self.fail_create=False;self.bad_confirm=False;self.offsets=[]
    def upload(self, media): return media
    def check(self): pass
    def ensure_capacity(self,n): return {'posts':{'remaining':20,'used':0,'limit':20}}
    def wait(self,p): pass
    def call(self,path,method='GET',data=None):
        if path.startswith('/post/?'):
            self.offsets.append(path)
            return {'items':copy.deepcopy(self.posts),'total':len(self.posts)}
        if method=='POST':
            payload=json.loads(data)
            assert len(payload['data']['SNAPCHAT']['uploadIds'])==1
            n=len(self.posts)+1;u=payload['data']['SNAPCHAT']['uploadIds'][0]
            row=payload|{'id':f'p{n}','status':'POSTED','externalData':{'SNAPCHAT':{'status':'PUBLISHED','mediaIds':[f'm{n}'],'sourceUploadIds':[u]}}}
            self.posts.append(row)
            if self.fail_create: raise b.BundleError('timeout after provider accepted')
            return row
        row=copy.deepcopy(next(x for x in self.posts if x['id']==path.split('/')[-1]))
        if self.bad_confirm: row['externalData']['SNAPCHAT']['sourceUploadIds']=['wrong']
        return row

def recover(c,j):
    from publishing_v2.group_recovery import recover_rejected_group
    return recover_rejected_group(c,j,'identity','title',2)

def test_recovery_reuses_ordered_uploads_and_is_idempotent():
    c,j=Client(),Journal();recover(c,j);recover(c,j)
    assert [p['data']['SNAPCHAT']['uploadIds'] for p in c.posts]==[['u1'],['u2']]
    assert [j.state[str(i)]['media_id'] for i in (1,2)]==['m1','m2']
    assert j.state['_group']['draft_validation']['error']==ERROR

def test_only_specific_confirmed_validation_rejection_allows_recovery():
    c,j=Client(),Journal();j.state['_group']['draft_validation']['error']='unknown error'
    with pytest.raises(b.BundleError): recover(c,j)
    assert not c.posts

def test_ambiguous_recovery_create_is_adopted_without_duplicate():
    c,j=Client(),Journal();c.fail_create=True
    with pytest.raises(b.BundleError): recover(c,j)
    c.fail_create=False;recover(c,j)
    assert len(c.posts)==2
    assert j.state['1']['post_id']=='p1'

def test_unmatched_ambiguous_intent_stays_blocked():
    c,j=Client(),Journal();c.fail_create=True
    with pytest.raises(b.BundleError): recover(c,j)
    c.posts=[];c.fail_create=False
    with pytest.raises(b.BundleError): recover(c,j)
    assert not c.posts

def test_journal_failure_prevents_public_create():
    c,j=Client(),Journal();j.fail=True
    with pytest.raises(b.BundleError): recover(c,j)
    assert not c.posts

def test_existing_group_or_foreign_overlap_blocks_recovery():
    c,j=Client(),Journal();c.posts=[{'id':'old','teamId':'team','status':'POSTED','data':{'SNAPCHAT':{'type':'STORY','uploadIds':['u1','u2']}}}]
    with pytest.raises(b.BundleError): recover(c,j)
    assert len(c.posts)==1

def test_delivery_mismatch_not_posted_and_second_card_not_sent():
    c,j=Client(),Journal();c.bad_confirm=True
    with pytest.raises(b.BundleError): recover(c,j)
    assert len(c.posts)==1 and j.state['1']['status']!='POSTED'

def test_normal_two_card_publish_sends_one_upload_per_request(monkeypatch):
    c,j=Client(),Journal();j.state={}
    monkeypatch.setattr(b,'BundleClient',lambda:c)
    monkeypatch.setattr(b,'GitHubJournal',lambda identity:j)
    monkeypatch.setattr(b,'load_package',lambda path:('identity','title',['u1','u2']))
    # This test covers request grouping; readability failures have separate CLI tests.
    monkeypatch.setattr('publishing_v2.readability.require_for_new_delivery', lambda *args: None)
    monkeypatch.setattr(b.Path,'read_text',lambda self:'{}')
    monkeypatch.setattr('sys.argv',['publisher','publish','--manifest','test.json'])
    b.main()
    assert len(c.posts)==2
