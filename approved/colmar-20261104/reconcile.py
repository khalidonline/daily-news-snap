"""Recover the exact STORY receipt after GitHub's HTTP500; never send media."""
from datetime import datetime,timezone
from publishing_v2.bundle_api import BundleClient,GitHubJournal,BundleError
from publishing_v2.group_recovery import inventory
IDENTITY='f21f24ffedf2769b62dd85e6a4e409b7d479d47b4ce4ce7c1bd7c53fa6c6232a'
UPLOAD='7a64cbcd-7f64-4e77-bc4a-d9062ee1da73'
def reconcile(client,journal):
    state=journal.read();saved=state.get('1',{})
    if saved.get('upload_id')!=UPLOAD or saved.get('placement')!='STORY':raise BundleError('Unexpected recovery identity')
    rows=inventory(client)
    matches=[r for r in rows if UPLOAD in ((r.get('data') or {}).get('SNAPCHAT') or {}).get('uploadIds',[])]
    if len(matches)!=1:raise BundleError('Expected exactly one existing upload match; no new send')
    post=client.call('/post/'+matches[0]['id']);snap=(post.get('data') or {}).get('SNAPCHAT') or {};ext=(post.get('externalData') or {}).get('SNAPCHAT') or {}
    if (post.get('teamId')!=client.team or post.get('id')!=matches[0]['id'] or post.get('deletedAt')
        or post.get('status')!='POSTED' or snap.get('type')!='STORY' or snap.get('uploadIds')!=[UPLOAD]
        or ext.get('status')!='PUBLISHED' or ext.get('sourceUploadIds')!=[UPLOAD]
        or ext.get('profileId')!='cd0ffc18-1462-4f19-a1ae-8c91174faaa7'
        or (saved.get('post_id') and saved['post_id']!=post['id'])):
        raise BundleError('Exact existing STORY not confirmed; no new send')
    saved.update(post_id=post['id'],status='POSTED')
    state['recovery']={'at':datetime.now(timezone.utc).isoformat(),'reason':'GitHub HTTP500 saving created post ID','inventory_count':len(rows),'matched_upload_id':UPLOAD,'post_id':post['id'],'snapchat_status':'PUBLISHED','provider_mutations':0}
    journal.save(state)
    print('Reconciled existing STORY '+post['id'])
if __name__=='__main__':
    client=BundleClient();client.check();reconcile(client,GitHubJournal(IDENTITY))
