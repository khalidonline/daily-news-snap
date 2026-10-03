"""Save reviewed, already POSTED packages; never produce or repost daily Snaps.
Archive approval is separate from the original time-limited daily approval.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
from .bundle_api import BundleClient, BundleError, GitHubJournal, HTTPFailure

def now(): return datetime.now(timezone.utc).isoformat()

class SavedJournal(GitHubJournal):
    def __init__(self, identity):
        super().__init__(identity)
        self.path='/contents/saved-story-receipts/'+identity+'.json'

class SavedClient(BundleClient):
    def find(self, identity, title, uploads):
        matches=[]; offset=0
        while True:
            result=self.call('/post/?'+urllib.parse.urlencode({'teamId':self.team,'offset':offset,'limit':100}))
            items=result.get('items'); total=result.get('total')
            if not isinstance(items,list) or type(total) is not int: raise BundleError('Incomplete provider inventory')
            for row in items:
                if row.get('teamId')!=self.team: raise BundleError('Provider team mismatch')
                snap=(row.get('data') or {}).get('SNAPCHAT') or {}
                if row.get('status')=='DELETED' or row.get('deletedAt'): continue
                same_key=row.get('referenceKey')=='saved-'+identity
                same_media=snap.get('type')=='SAVED_STORY' and snap.get('uploadIds')==uploads
                if same_key or same_media:
                    if snap.get('type')!='SAVED_STORY' or snap.get('uploadIds')!=uploads: raise BundleError('Saved Story identity collision')
                    matches.append(row['id'])
                elif snap.get('type')=='SAVED_STORY' and (snap.get('title')==title or set(snap.get('uploadIds') or []) & set(uploads)):
                    raise BundleError('Overlapping Saved Story needs reconciliation')
            offset+=len(items)
            if offset>=total: return matches
            if not items or offset>10000: raise BundleError('Incomplete provider inventory')

    def create_saved(self, identity, title, uploads):
        payload={'teamId':self.team,'title':title,'referenceKey':'saved-'+identity,
                 'postDate':now(),'status':'SCHEDULED','socialAccountTypes':['SNAPCHAT'],
                 'data':{'SNAPCHAT':{'type':'SAVED_STORY','title':title,'uploadIds':uploads}}}
        result=self.call('/post/','POST',json.dumps(payload).encode())
        if not result.get('id'): raise BundleError('Ambiguous Saved Story create; do not retry')
        return result['id']

    def confirm(self, post_id, title, uploads):
        self.wait(post_id)
        row=self.call('/post/'+urllib.parse.quote(post_id,safe=''))
        snap=(row.get('data') or {}).get('SNAPCHAT') or {}
        if (row.get('teamId')!=self.team or row.get('id')!=post_id or row.get('status')!='POSTED'
            or snap.get('type')!='SAVED_STORY' or snap.get('uploadIds')!=uploads or snap.get('title')!=title):
            raise BundleError('Saved Story result mismatch')
        return {'id':post_id,'status':'POSTED','externalData':row.get('externalData')}

def save_story(client,journal,identity,title,uploads):
    state=journal.read()
    if state and (state.get('identity')!=identity or state.get('upload_ids')!=uploads):
        raise BundleError('Saved Story journal identity mismatch')
    if state.get('status')=='POSTED': return state
    found=client.find(identity,title,uploads)
    if len(found)>1: raise BundleError('Multiple existing Saved Stories; reconcile first')
    if found:
        if state.get('post_id') and state['post_id']!=found[0]: raise BundleError('Saved Story receipt collision')
        state={'identity':identity,'title':title,'upload_ids':uploads,'post_id':found[0],'status':'RECONCILING'}
        journal.save(state)
    if state and not state.get('post_id'): raise BundleError('Ambiguous previous intent; no new request')
    if not state:
        client.ensure_capacity(1)
        state={'identity':identity,'title':title,'upload_ids':uploads,'status':'SENDING','intent_at':now()}
        journal.save(state)
        state['post_id']=client.create_saved(identity,title,uploads)
        journal.save(state)
    result=client.confirm(state['post_id'],title,uploads)
    state.update(status='POSTED',confirmed_at=now(),provider_result=result)
    journal.save(state)
    return state

def validate_archive(approval, source):
    if approval.get('approved') is not True or approval.get('account')!='executivesaudi' or not approval.get('empty_profile_confirmation'):
        raise BundleError('Independent archive approval and profile baseline required')
    expiry=datetime.fromisoformat(approval['expires_at'].replace('Z','+00:00'))
    if expiry<=datetime.now(timezone.utc): raise BundleError('Archive approval expired')
    path=Path(approval['manifest']); raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=approval['manifest_sha256']: raise BundleError('Archive manifest changed')
    manifest=json.loads(raw)
    if manifest.get('approved') is not True or manifest.get('account')!='executivesaudi': raise BundleError('Original package not approved')
    frames=manifest['media']
    if not 1<=len(frames)<=10: raise BundleError('Invalid archive count')
    selected=approval.get('public_indices',list(range(1,len(frames)+1)))
    if not selected or selected!=sorted(set(selected)) or any(type(i) is not int or not 1<=i<=len(frames) for i in selected):
        raise BundleError('Invalid public card selection')
    reviewed=approval.get('reviewed_public_sha256',[])
    for i,f in enumerate(frames,1):
        if i in selected:
            if f.get('kind') not in ('info','story','topic') and not (f.get('kind') is None and f['sha256'] in reviewed):
                raise BundleError('Non-public archive media')
        elif f.get('kind')!='credits':
            raise BundleError('Cannot omit story content')
    hashes=[]
    for f in frames:
        p=Path(f['path'])
        if p.is_absolute() or '..' in p.parts or p.suffix.lower() not in ('.jpg','.png','.jpeg'): raise BundleError('Invalid archive media')
        content=p.read_bytes() if p.exists() else base64.b64decode(Path(str(p)+'.b64').read_bytes(),validate=False)
        digest=hashlib.sha256(content).hexdigest()
        if digest!=f['sha256']: raise BundleError('Archive media changed')
        hashes.append(digest)
    identity=hashlib.sha256(('executivesaudi:'+':'.join(hashes)).encode()).hexdigest()
    if identity!=approval['identity'] or len(set(hashes))!=len(hashes): raise BundleError('Archive identity mismatch')
    if source.get('reconciliation') or set(k for k in source if k.isdigit())!={str(i+1) for i in range(len(frames))}: raise BundleError('Source receipt not final')
    rows=[source[str(i+1)] for i in range(len(frames))]
    if any(r.get('status')!='POSTED' or not r.get('post_id') or not r.get('upload_id') for r in rows): raise BundleError('Incomplete original publication')
    return identity,approval.get('title') or manifest['title'],[rows[i-1] for i in selected]

def main():
    p=argparse.ArgumentParser();p.add_argument('--approval',required=True);a=p.parse_args()
    approval=json.loads(Path(a.approval).read_text())
    source_journal=GitHubJournal(approval['identity']); source=source_journal.read()
    identity,title,rows=validate_archive(approval,source)
    c=SavedClient();c.check()
    for r in rows:
        if r.get('group_upload_ids'):
            c.confirm_group(r['post_id'], r['group_upload_ids'])
        live=c.call('/post/'+urllib.parse.quote(r['post_id'],safe=''))
        snap=(live.get('data') or {}).get('SNAPCHAT') or {}
        if (live.get('id')!=r['post_id'] or live.get('teamId')!=c.team or live.get('status')!='POSTED'
            or live.get('deletedAt') or snap.get('type','STORY')!='STORY' or snap.get('uploadIds')!=r.get('group_upload_ids',[r['upload_id']])
            or r['upload_id'] not in snap.get('uploadIds',[])):
            raise BundleError('Original publication no longer matches approved receipt')
    result=save_story(c,SavedJournal(identity),identity,title,[r['upload_id'] for r in rows])
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__': main()
