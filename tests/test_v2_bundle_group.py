import copy
import pytest
from publishing_v2 import bundle_api as b

class Journal:
    def __init__(self): self.state={}
    def read(self): return copy.deepcopy(self.state)
    def save(self,s): self.state=copy.deepcopy(s)
class Client:
    team='team'
    def __init__(self): self.sent=[]; self.n=0; self.reverse=False; self.fail=False
    def ensure_capacity(self,n): return {'date':'2026-10-03','posts':{'used':len(self.sent),'remaining':20-len(self.sent)}}
    def upload(self,m): self.n+=1; return 'u'+str(self.n)
    def create_group(self,title,uploads,key):
        self.sent.append(uploads)
        if self.fail: raise b.BundleError('ambiguous')
        return 'p'
    def confirm_group(self,p,uploads):
        if self.reverse: raise b.BundleError('order mismatch')
        return ['s1','s2']

def test_group_single_create_and_repeat_no_send():
    c,j=Client(),Journal()
    b.publish_group(c,j,'title',['a','b'],'identity')
    b.publish_group(c,j,'title',['a','b'],'identity')
    assert c.sent==[['u1','u2']]
    assert j.state['1']['media_id']=='s1' and j.state['2']['media_id']=='s2'
    assert j.state['_group']['quota_after']['posts']['used']==1

def test_ambiguous_group_never_recreated():
    c,j=Client(),Journal(); c.fail=True
    with pytest.raises(b.BundleError): b.publish_group(c,j,'title',['a','b'],'identity')
    with pytest.raises(b.BundleError): b.publish_group(c,j,'title',['a','b'],'identity')
    assert len(c.sent)==1

def test_existing_card_receipt_blocks_group_conversion():
    c,j=Client(),Journal(); j.state={'1':{'post_id':'old','status':'POSTED'}}
    with pytest.raises(b.BundleError): b.publish_group(c,j,'title',['a','b'],'identity')
    assert not c.sent

def test_unconfirmed_order_not_marked_posted():
    c,j=Client(),Journal(); c.reverse=True
    with pytest.raises(b.BundleError): b.publish_group(c,j,'title',['a','b'],'identity')
    assert j.state['_group']['status']!='POSTED'

def test_payload_one_week_and_two_ordered_uploads(monkeypatch):
    monkeypatch.setenv('BUNDLE_API_KEY','test'); monkeypatch.setenv('BUNDLE_TEAM_ID','team')
    c=b.BundleClient(); calls=[]
    def call(path,method='GET',data=None):
        import json
        calls.append(json.loads(data)); return {'id':'p'}
    c.call=call
    assert c.create_group('title',['u1','u2'],'story-key')=='p'
    assert calls[0]['data']['SNAPCHAT']=={'type':'STORY','uploadIds':['u1','u2'],'storyDuration':'ONE_WEEK'}
    assert calls[0]['referenceKey']=='story-key'

def test_provider_confirmation_requires_order_and_all_media(monkeypatch):
    monkeypatch.setenv('BUNDLE_API_KEY','test'); monkeypatch.setenv('BUNDLE_TEAM_ID','team')
    c=b.BundleClient(); c.wait=lambda p: None
    row={'id':'p','teamId':'team','status':'POSTED','data':{'SNAPCHAT':{'type':'STORY','uploadIds':['u1','u2'],'storyDuration':'ONE_WEEK'}},'externalData':{'SNAPCHAT':{'mediaIds':['m1','m2'],'sourceUploadIds':['u1','u2'],'status':'PUBLISHED'}}}
    c.call=lambda p: row
    assert c.confirm_group('p',['u1','u2'])==['m1','m2']
    row['externalData']['SNAPCHAT']['sourceUploadIds'].reverse()
    with pytest.raises(b.BundleError): c.confirm_group('p',['u1','u2'])

def test_legacy_publisher_cannot_resume_group():
    c,j=Client(),Journal(); c.fail=True
    with pytest.raises(b.BundleError): b.publish_group(c,j,'title',['a','b'],'identity')
    with pytest.raises(b.BundleError): b.publish(c,j,'title',['a','b'])
    assert len(c.sent)==1
