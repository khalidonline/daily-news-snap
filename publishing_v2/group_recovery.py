"""Explicit recovery of a provider-rejected multi-upload STORY, without re-upload.

Keep the failed intent. Only the observed Max-1 validation rejection plus a full
fresh provider inventory permits conversion. Ambiguous individual sends are
reconciled by exact key/media or stay blocked; never recreated.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.parse
from .bundle_api import BundleClient, BundleError, GitHubJournal, load_package, check_predecessors


def inventory(client):
    rows=[];offset=0
    while True:
        result=client.call('/post/?'+urllib.parse.urlencode({'teamId':client.team,'offset':offset,'limit':100}))
        items=result.get('items');total=result.get('total')
        if not isinstance(items,list) or type(total) is not int or total<0:
            raise BundleError('Incomplete reconciliation inventory')
        if any(row.get('teamId')!=client.team for row in items):
            raise BundleError('Wrong inventory team')
        rows.extend(items);offset+=len(items)
        if offset>=total:
            if len({r.get('id') for r in rows})!=len(rows):
                raise BundleError('Duplicate inventory page; no create')
            return rows
        if not items or offset>10000: raise BundleError('Incomplete reconciliation inventory')


def confirm_card(client, post_id, upload, key):
    client.wait(post_id)
    row=client.call('/post/'+urllib.parse.quote(post_id,safe=''))
    snap=(row.get('data') or {}).get('SNAPCHAT') or {}
    ext=(row.get('externalData') or {}).get('SNAPCHAT') or {}
    ids=ext.get('mediaIds') or []
    if (row.get('id')!=post_id or row.get('teamId')!=client.team
        or row.get('status')!='POSTED' or row.get('deletedAt')
        or row.get('referenceKey')!=key or snap.get('type')!='STORY'
        or snap.get('storyDuration')!='ONE_WEEK' or snap.get('uploadIds')!=[upload]
        or ext.get('status')!='PUBLISHED' or ext.get('sourceUploadIds')!=[upload]
        or len(ids)!=1 or not isinstance(ids[0],str) or not ids[0]):
        raise BundleError('Single-card delivery not verified')
    return ids[0]


def recover_rejected_group(client,journal,identity,title,card_count):
    state=journal.read();group=state.get('_group') or {}
    uploads=group.get('uploads') or []
    rejection=group.get('draft_validation') or {}
    try: issues=json.loads(rejection.get('error','')).get('issues',[])
    except (ValueError,TypeError): issues=[]
    allowed=any(i.get('message')=='Max 1 upload(s) allowed' and i.get('path')==['data','SNAPCHAT','uploadIds'] for i in issues)
    if (group.get('identity')!=identity or group.get('post_id')
        or group.get('reference_key')!='story-'+identity or len(uploads)!=card_count
        or card_count!=2 or len(set(uploads))!=2
        or rejection.get('status')!='REJECTED' or rejection.get('http_status')!=400 or not allowed):
        raise BundleError('Confirmed single-upload rejection required; no automatic fallback')
    client.check();rows=inventory(client)
    recovery=group.get('single_recovery')
    expected_keys={u:f'story-{identity}-card-{i}' for i,u in enumerate(uploads,1)}
    matches={u:[] for u in uploads}
    for row in rows:
        snap=(row.get('data') or {}).get('SNAPCHAT') or {}
        us=snap.get('uploadIds') or [];key=row.get('referenceKey')
        overlap=set(us)&set(uploads)
        if key==group['reference_key']:
            raise BundleError('Original group exists; do not split')
        if overlap or key in expected_keys.values():
            if (len(us)!=1 or us[0] not in expected_keys or key!=expected_keys[us[0]]
                or snap.get('type')!='STORY' or row.get('deletedAt') or row.get('status')=='DELETED'):
                raise BundleError('Media overlap needs manual reconciliation')
            matches[us[0]].append(row)
    if any(len(v)>1 for v in matches.values()): raise BundleError('Duplicate provider matches')
    if not recovery:
        if any(matches.values()) or any(state.get(str(i),{}).get('post_id') for i in (1,2)):
            raise BundleError('Unexpected existing post before recovery')
        client.ensure_capacity(card_count+2)
        group['single_recovery']={'started_at':datetime.now(timezone.utc).isoformat(),
            'inventory_total':len(rows),'original_rows':copy.deepcopy({str(i):state.get(str(i)) for i in (1,2)})}
        group['status']='RECOVERING_SINGLES'
        for i,u in enumerate(uploads,1):
            state[str(i)]={'status':'PENDING','upload_id':u,'reference_key':expected_keys[u]}
        journal.save(state)
    missing=0
    for i,u in enumerate(uploads,1):
        row=state[str(i)];found=matches[u]
        if row.get('upload_id')!=u or row.get('reference_key')!=expected_keys[u]: raise BundleError('Recovery identity changed')
        if found:
            if row.get('post_id') and row['post_id']!=found[0]['id']: raise BundleError('Receipt collision')
            row['post_id']=found[0]['id'];journal.save(state)
        elif row.get('post_id') or row.get('status')!='PENDING':
            raise BundleError('Ambiguous single-card intent; do not recreate')
        else: missing+=1
    if missing: client.ensure_capacity(missing+2)
    for i,u in enumerate(uploads,1):
        row=state[str(i)]
        if not row.get('post_id'):
            row.update(status='SENDING',intent_at=datetime.now(timezone.utc).isoformat());journal.save(state)
            payload={'teamId':client.team,'title':f'{title} [{i}/{card_count}]','referenceKey':expected_keys[u],
                'postDate':datetime.now(timezone.utc).isoformat(),'status':'SCHEDULED','socialAccountTypes':['SNAPCHAT'],
                'data':{'SNAPCHAT':{'type':'STORY','uploadIds':[u],'storyDuration':'ONE_WEEK'}}}
            result=client.call('/post','POST',json.dumps(payload).encode())
            if not result.get('id'): raise BundleError('Ambiguous create; reconcile before retry')
            row['post_id']=result['id'];journal.save(state)
        media_id=confirm_card(client,row['post_id'],u,expected_keys[u])
        if any(state[str(k)].get('media_id')==media_id for k in range(1,i)):
            raise BundleError('Duplicate Snapchat media ID')
        row.update(status='POSTED',media_id=media_id,confirmed_at=datetime.now(timezone.utc).isoformat());journal.save(state)
        print(f'Card {i}/{card_count}: POSTED ({row["post_id"]}; Snapchat {media_id})')
    group['status']='RECOVERED_AS_SINGLE_POSTS';journal.save(state)
    return state


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);args=parser.parse_args()
    identity,title,media=load_package(args.manifest)
    manifest=json.loads(Path(args.manifest).read_text())
    now=datetime.now(timezone.utc)
    not_before=datetime.fromisoformat(manifest['not_before'].replace('Z','+00:00'))
    if not_before.tzinfo is None or now<not_before: raise BundleError('Not yet approved for delivery')
    check_predecessors(manifest.get('predecessors',[]))
    recover_rejected_group(BundleClient(),GitHubJournal(identity),identity,title,len(media))

if __name__=='__main__':main()
