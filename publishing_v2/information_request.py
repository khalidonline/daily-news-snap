"""Explicit hash-bound approval requests; no rendering or provider API calls."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import tempfile
from .prepared_information import (package_path, read_json, digest, verify_prepared,
                                   content_digest)

REQUEST_PATH = '.github/information-publish-request.json'
DESTINATIONS = ['STORY', 'SAVED_STORY']

def checked_path(root, relative):
    root=Path(root).resolve(); rel=Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Unsafe request path')
    p=root
    for part in rel.parts:
        p=p/part
        if p.is_symlink(): raise ValueError('Symlink is not an approved file')
    if not p.resolve().is_relative_to(root): raise ValueError('Path escapes root')
    return p

def resolve_push(root, event, now):
    """Validate an exact push checkout; no publication or secret access here."""
    root=Path(root).resolve()
    if (event.get('ref')!='refs/heads/main' or event.get('repository',{}).get('full_name')!='khalidonline/daily-news-snap'
        or event.get('deleted') is not False or event.get('forced') is not False):
        raise ValueError('Expected non-forced main push')
    before,after=event.get('before',''),event.get('after','')
    if any(not re.fullmatch('[0-9a-f]{40}',v) or v=='0'*40 for v in (before,after)):
        raise ValueError('Invalid push range')
    if git(root,'rev-parse','HEAD').decode().strip()!=after: raise ValueError('Checkout differs from push')
    subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',before,after],
                   check=True,capture_output=True,timeout=30)
    changed=git(root,'diff','--name-only','-z',before,after).decode().split('\0')
    if REQUEST_PATH not in changed: raise ValueError('No explicit request in push')
    raw=checked_path(root,REQUEST_PATH).read_bytes()
    if raw!=git(root,'show',after+':'+REQUEST_PATH): raise ValueError('Request differs from event commit')
    request=json.loads(raw)
    package=validate_request(root,request,now)
    # All inputs must be the event-commit bytes, not local modifications.
    receipt=read_json(package/'preview-receipt.json')
    paths=set(receipt['files']) | {str((package/n).relative_to(root)) for n in ('prepared.json','preview-receipt.json')}
    for relative in paths:
        if checked_path(root,relative).read_bytes()!=git(root,'show',after+':'+relative):
            raise ValueError('Package differs from event commit')
    return package

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='mode',required=True)
    auth=sub.add_parser('authorize');auth.add_argument('--package',required=True)
    auth.add_argument('--owner-reference',required=True);auth.add_argument('--output',required=True)
    push=sub.add_parser('resolve-push');push.add_argument('--event',required=True)
    args=parser.parse_args();now=datetime.now(timezone.utc)
    if args.mode=='authorize':
        path=checked_package(Path.cwd(),args.package)
        print(authorize_request(path,args.owner_reference,now,args.output))
    else:
        package=resolve_push(Path.cwd(),json.loads(Path(args.event).read_text()),now)
        print('package='+package.name)

def date(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None: raise ValueError('Timezone required')
    return result

def checked_package(root, name):
    if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,80}',name):
        raise ValueError('Invalid package name')
    if Path(root).resolve()!=Path.cwd().resolve():
        raise ValueError('Run from repository root')
    return package_path(checked_path(root,'approved/'+name))

def provenance(manifest):
    # Reference metadata is archival (sources.json), not a posting gate.
    # Retain source assets so preparation still seals the selected image bytes.
    for frame in manifest['media']:
        if not frame.get('source_assets'): raise ValueError('Source provenance required before preview')

def expected_files(p, record):
    return set(record['assets']) | {str((p/n).relative_to(Path.cwd())) for n in
            ('manifest.json','archive-approval.json','design-review.json','sources.json')} | {'publishing_v2/design-settings.json'}

def check_receipt(p, record):
    receipt=read_json(checked_path(Path.cwd(),str((p/'preview-receipt.json').relative_to(Path.cwd()))))
    if (receipt.get('version')!=1 or receipt.get('status')!='UPLOADED_PREVIEW_READY_NOT_AUTHORIZED'
        or receipt.get('repository')!='khalidonline/daily-news-snap' or receipt.get('branch')!='main'
        or not re.fullmatch('[0-9a-f]{40}',receipt.get('commit',''))):
        raise ValueError('Verified uploaded preview receipt required')
    if set(receipt.get('files',{}))!=expected_files(p,record):
        raise ValueError('Incomplete preview file set')
    expected=dict(record);expected.pop('preparation_seconds',None)
    if receipt.get('prepared_content')!=expected: raise ValueError('Preview preparation changed')
    return receipt

def identity(manifest):
    return digest(('executivesaudi:'+':'.join(f['sha256'] for f in manifest['media'])).encode())

def encode(value): return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()

def authorize_request(package_dir, owner_reference, now, output_dir):
    """Stage three files in a NEW directory; never modify source draft or post."""
    p=package_path(package_dir);root=Path.cwd()
    if not isinstance(owner_reference,str) or len(owner_reference.strip())<8:
        raise ValueError('Explicit owner reference required')
    if now.tzinfo is None: raise ValueError('Timezone required')
    record=verify_prepared(p);receipt=check_receipt(p,record)
    for relative,sha in receipt['files'].items():
        if digest(checked_path(root,relative).read_bytes())!=sha:
            raise ValueError('Preview bytes changed')
    m=read_json(p/'manifest.json');a=read_json(p/'archive-approval.json')
    if m.get('approved') is not False or a.get('approved') is not False:
        raise ValueError('Fresh draft required; retry existing approved request instead')
    if not date(m['not_before'])<=now<date(m['expires_at']): raise ValueError('Approval window invalid')
    if a.get('expires_at')!=m['expires_at'] or a.get('identity')!=identity(m):
        raise ValueError('Archive identity/window mismatch')
    provenance(m)
    m['approved']=True;m['owner_review'].update(reference=owner_reference,reviewed_at=now.isoformat())
    a.update(approved=True,owner_authorization=owner_reference,manifest_sha256=digest(encode(m)))
    request=dict(version=1,package=p.name,identity=identity(m),destinations=DESTINATIONS,
                 owner_reference=owner_reference,approved_at=now.isoformat(),expires_at=m['expires_at'],
                 manifest_sha256=digest(encode(m)),archive_sha256=digest(encode(a)),
                 prepared_sha256=digest((p/'prepared.json').read_bytes()),
                 preview_receipt_sha256=digest((p/'preview-receipt.json').read_bytes()))
    out=Path(output_dir).absolute()
    if out.exists() or out.is_symlink(): raise ValueError('Staging output already exists')
    if out.is_relative_to(p): raise ValueError('Stage outside original package')
    if any(parent.is_symlink() for parent in out.parents): raise ValueError('Unsafe output parent')
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.approval-stage-',dir=out.parent) as temporary:
        temp=Path(temporary)
        for rel,raw in [(str((p/'manifest.json').relative_to(root)),encode(m)),
                        (str((p/'archive-approval.json').relative_to(root)),encode(a)),
                        (REQUEST_PATH,encode(request))]:
            dest=temp/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        # Atomic directory install; never overwrite a pre-existing destination.
        if out.exists(): raise ValueError('Staging collision')
        temp.rename(out)
    return out

def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.PIPE,timeout=30)

def validate_request(root, request, now):
    root=Path(root).resolve();r=request
    if r.get('version')!=1 or r.get('destinations')!=DESTINATIONS:
        raise ValueError('Unsupported request')
    p=checked_package(root,r.get('package'))
    record=verify_prepared(p);receipt=check_receipt(p,record)
    for filename,key in [('manifest.json','manifest_sha256'),('archive-approval.json','archive_sha256'),
                         ('prepared.json','prepared_sha256'),('preview-receipt.json','preview_receipt_sha256')]:
        if digest(checked_path(root,str((p/filename).relative_to(root))).read_bytes())!=r.get(key):
            raise ValueError('Request bytes changed')
    m=read_json(p/'manifest.json');a=read_json(p/'archive-approval.json')
    if m.get('approved') is not True or a.get('approved') is not True: raise ValueError('Both approvals required')
    reference=r.get('owner_reference')
    if not isinstance(reference,str) or len(reference.strip())<8: raise ValueError('Owner reference required')
    if (m['owner_review'].get('reference')!=reference or a.get('owner_authorization')!=reference
        or m['owner_review'].get('reviewed_at')!=r.get('approved_at')):
        raise ValueError('Approval reference mismatch')
    if (r.get('expires_at')!=m['expires_at'] or a.get('expires_at')!=m['expires_at']
        or not date(m['not_before'])<=date(r['approved_at'])<=now<date(r['expires_at'])):
        raise ValueError('Approval expired or future')
    if (r.get('identity')!=identity(m) or a.get('identity')!=identity(m)
        or a.get('manifest')!=str((p/'manifest.json').relative_to(root))
        or a.get('manifest_sha256')!=r['manifest_sha256']
        or a.get('public_indices')!=list(range(1,len(m['media'])+1))):
        raise ValueError('Destination identity mismatch')
    provenance(m)
    # Verify the real immutable draft, not only agent-supplied hashes.
    subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',receipt['commit'],'HEAD'],
                   check=True,capture_output=True,timeout=30)
    for relative,sha in receipt['files'].items():
        local=checked_path(root,relative).read_bytes()
        old=git(root,'show',receipt['commit']+':'+relative)
        if digest(old)!=sha: raise ValueError('Preview receipt differs from Git draft')
        if relative==str((p/'manifest.json').relative_to(root)):
            draft=json.loads(old)
            if draft.get('approved') is not False or content_digest(draft)!=content_digest(m):
                raise ValueError('Only authorization may change after preview')
        elif relative==str((p/'archive-approval.json').relative_to(root)):
            draft=json.loads(old)
            if draft.get('approved') is not False or content_digest(draft,True)!=content_digest(a,True):
                raise ValueError('Archive content changed after preview')
        elif digest(local)!=sha: raise ValueError('Preview content changed')
    return p

if __name__=='__main__': main()
