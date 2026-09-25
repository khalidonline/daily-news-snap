"""Manual publishing of approved media; no generation and no browser login.

A remote compare-and-swap journal is committed BEFORE each public mutation.
An ambiguous create is never retried automatically.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from .publication import publication_indices, validate_public_attribution


class BundleError(RuntimeError):
    pass


class HTTPFailure(BundleError):
    def __init__(self, code):
        self.code = code
        super().__init__(f'API HTTP {code}; inspect provider dashboard if needed')


def request(url, headers, method='GET', data=None):
    # Do not log response bodies, credentials, or raw transport exceptions.
    req = urllib.request.Request(url, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise HTTPFailure(exc.code) from None
    except (OSError, ValueError):
        raise BundleError('API connection or response failure; do not blindly retry publishing') from None


def verify_account(account, team):
    if ((account.get('username') or '').lstrip('@').lower() != 'executivesaudi'
            or account.get('teamId') != team or account.get('type') != 'SNAPCHAT'
            or not account.get('id') or account.get('deletedAt') or account.get('deleteOn')):
        raise BundleError('Expected active Snapchat account executivesaudi is not connected')


class BundleClient:
    def __init__(self):
        self.key = os.environ.get('BUNDLE_API_KEY', '').strip()
        self.team = os.environ.get('BUNDLE_TEAM_ID', '').strip()
        if not self.key or not self.team:
            raise BundleError('Missing BUNDLE_API_KEY or BUNDLE_TEAM_ID repository secret')

    def call(self, path, method='GET', data=None, content_type='application/json'):
        return request('https://api.bundle.social/api/v1' + path,
                       {'x-api-key': self.key, 'Content-Type': content_type,
                        'User-Agent':'ExecutiveSaudiPublisher/1.0', 'Accept':'application/json'}, method, data)

    def check(self):
        query = urllib.parse.urlencode({'type':'SNAPCHAT','teamId':self.team})
        verify_account(self.call('/social-account/by-type?' + query), self.team)

    def ensure_capacity(self, count, *, now=None):
        if type(count) is not int or count < 0:
            raise BundleError('invalid_required_capacity')
        if not count: return
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None: raise BundleError('quota_requires_timezone')
        day = now.astimezone(timezone.utc).date()
        account = self.call('/social-account/by-type?' + urllib.parse.urlencode(
            {'type':'SNAPCHAT','teamId':self.team}))
        verify_account(account, self.team)
        usage = self.call('/organization/usage/daily-limits?' + urllib.parse.urlencode(
            {'socialAccountId':account['id'], 'date':day.isoformat()}))
        try:
            stamp = datetime.fromisoformat(usage['date'].replace('Z','+00:00'))
            posts = usage['posts']
            used, limit, remaining = (posts[k] for k in ('used','limit','remaining'))
            valid = (usage['socialAccountId'] == account['id'] and usage['type'] == 'SNAPCHAT'
                and stamp.tzinfo is not None and stamp.astimezone(timezone.utc).date() == day
                and all(type(v) is int and v >= 0 for v in (used,limit,remaining))
                and remaining == max(0,limit-used))
        except (KeyError, TypeError, ValueError, AttributeError):
            valid = False
        if not valid: raise BundleError('invalid_daily_quota_response')
        if remaining < count:
            raise BundleError(f'daily_quota_insufficient: need {count}, remaining {remaining}, UTC {day}')
        return usage

    def upload(self, media):
        path, content = media
        boundary = 'snap' + uuid.uuid4().hex
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="teamId"\r\n\r\n'
                f'{self.team}\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                f'filename="media{path.suffix.lower()}"\r\nContent-Type: {mime}\r\n\r\n').encode()
        result = self.call('/upload', 'POST', body + content + f'\r\n--{boundary}--\r\n'.encode(),
                           f'multipart/form-data; boundary={boundary}')
        if not result.get('id'): raise BundleError('Upload returned no ID')
        return result['id']

    def create(self, title, upload):
        payload = {'teamId':self.team, 'title':title[:100],
                   'postDate':datetime.now(timezone.utc).isoformat(), 'status':'SCHEDULED',
                   'socialAccountTypes':['SNAPCHAT'],
                   'data':{'SNAPCHAT':{'type':'STORY','uploadIds':[upload]}}}
        result = self.call('/post', 'POST', json.dumps(payload).encode())
        if not result.get('id'): raise BundleError('Create returned no ID; manual reconciliation required')
        return result['id']

    def wait(self, post_id):
        for _ in range(36):
            result = self.call('/post/' + urllib.parse.quote(post_id, safe=''))
            if result.get('teamId') != self.team or result.get('id') != post_id:
                raise BundleError('Receipt identity mismatch')
            status = result.get('status')
            if status == 'POSTED': return
            if status not in ('SCHEDULED', 'PUBLISHING', 'PROCESSING', 'PENDING'):
                raise BundleError('Post not confirmed; inspect saved receipt before recovery')
            time.sleep(5)
        raise BundleError('Post still pending; rerun polls the saved ID without recreating it')


class GitHubJournal:
    """Single immutable package identity; writes use GitHub contents SHA CAS."""
    branch = 'snapchat-api-state'

    def __init__(self, package_id):
        token = os.environ.get('GITHUB_TOKEN', '')
        repo = os.environ.get('GITHUB_REPOSITORY', '')
        if not token or repo != 'khalidonline/daily-news-snap':
            raise BundleError('Publishing requires the configured GitHub Actions repository')
        self.base = 'https://api.github.com/repos/' + repo
        self.headers = {'Authorization':'Bearer ' + token, 'Accept':'application/vnd.github+json',
                        'Content-Type':'application/json', 'User-Agent':'snapchat-approved-publisher'}
        self.path = '/contents/api-receipts/' + package_id + '.json'
        self.sha = None
        try:
            self.call('/git/ref/heads/' + self.branch)
        except HTTPFailure as exc:
            if exc.code != 404: raise
            head = self.call('/git/ref/heads/main')['object']['sha']
            self.call('/git/refs', 'POST', {'ref':'refs/heads/' + self.branch, 'sha':head})

    def call(self, path, method='GET', payload=None):
        return request(self.base + path, self.headers, method,
                       None if payload is None else json.dumps(payload).encode())

    def read(self):
        try:
            result = self.call(self.path + '?ref=' + self.branch)
        except HTTPFailure as exc:
            if exc.code == 404: return {}
            raise
        self.sha = result['sha']
        return json.loads(base64.b64decode(result['content']))

    def save(self, state):
        payload = {'branch':self.branch, 'message':'Record Snapchat API delivery state',
                   'content':base64.b64encode(json.dumps(state).encode()).decode()}
        if self.sha: payload['sha'] = self.sha
        result = self.call(self.path, 'PUT', payload)
        self.sha = result['content']['sha']


def publish(client, journal, title, media):
    state = journal.read()
    # Reconcile every uncertain intent before any new upload in this batch.
    rows = [state.get(str(i+1)) for i in range(len(media))]
    if any(row is not None and not row.get('post_id') for row in rows):
        raise BundleError('Uncertain previous create; reconcile in Bundle before continuing')
    required = sum(row is None for row in rows)
    if required: client.ensure_capacity(required)
    for index, item in enumerate(media):
        key = str(index + 1)
        row = state.get(key)
        if row and row.get('status') == 'POSTED': continue
        if row and not row.get('post_id'):
            raise BundleError('Uncertain previous create; reconcile in Bundle before continuing')
        if not row:
            upload = client.upload(item)
            # Durable intent first: failure or cancellation after this point blocks recreation.
            state[key] = {'status':'SENDING', 'upload_id':upload}
            journal.save(state)
            try:
                post_id = client.create(f'{title} [{key}/{len(media)}]', upload)
            except HTTPFailure as error:
                # Keep the durable uncertain intent. A 403 is not permission to
                # regenerate media or to bypass reconciliation with a new hash.
                state[key]['error'] = {'operation': 'create', 'http_status': error.code,
                                       'at': datetime.now(timezone.utc).isoformat()}
                journal.save(state)
                raise
            state[key]['post_id'] = post_id
            journal.save(state)
        client.wait(state[key]['post_id'])
        state[key]['status'] = 'POSTED'
        journal.save(state)
        print(f'Card {key}/{len(media)}: POSTED ({state[key]["post_id"]})')


def check_predecessors(identities, journal_factory=GitHubJournal):
    """A new export cannot bypass an older unresolved delivery attempt.

    Reconciliation is a separately evidenced operator action, never inferred
    from a missing journal, a 403, or an absent post ID. This helper only reads.
    """
    for identity in identities:
        if (not isinstance(identity, str) or len(identity) != 64
                or any(c not in '0123456789abcdef' for c in identity)):
            raise BundleError('Invalid predecessor identity')
        state = journal_factory(identity).read()
        proof = state.get('reconciliation', {})
        rows = [v for k, v in state.items() if k.isdigit()]
        status = proof.get('status')
        try:
            checked = datetime.fromisoformat(proof['checked_at'].replace('Z', '+00:00'))
            valid_time = checked.tzinfo is not None and checked <= datetime.now(timezone.utc)
        except (KeyError, TypeError, ValueError):
            valid_time = False
        if (not rows or status not in {'NOT_CREATED', 'DELETED'} or not valid_time
                or not str(proof.get('evidence_url', '')).startswith('https://')
                or (status == 'NOT_CREATED' and any(row.get('post_id') for row in rows))):
            raise BundleError('Previous export needs documented provider reconciliation; no new post sent')


def load_package(manifest):
    root = Path.cwd().resolve()
    path = (root / manifest).resolve()
    if not path.is_relative_to(root): raise BundleError('Manifest must be in the repository')
    data = json.loads(path.read_text())
    if data.get('format') == 'apple-correction-v1':
        from .apple_correction import validate_review
        validate_review(path.parent)
    if data.get('approved') is not True or data.get('account') != 'executivesaudi':
        raise BundleError('An approved executivesaudi manifest is required')
    expires = datetime.fromisoformat(data['expires_at'].replace('Z','+00:00'))
    if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
        raise BundleError('Approval expired; recheck event timing and content')
    if data.get('format') == 'owner-generated-design-v1':
        from .owner_design import validate_owner_design
        return validate_owner_design(data, root)
    frames = data.get('media', [])
    if not 1 <= len(frames) <= 10: raise BundleError('Expected 1–10 approved media files')
    try:
        from .autopilot.policy import validate_image_variety
        validate_image_variety(frames)
        indices = publication_indices(frames)
    except ValueError as error:
        raise BundleError(str(error)) from None
    media, hashes = [], []
    for frame in frames:
        source = (root / frame['path']).resolve()
        if not source.is_relative_to(root) or source.suffix.lower() not in ('.png','.jpg','.jpeg','.mp4'):
            raise BundleError('Unsupported media path')
        if not 0 < source.stat().st_size <= 100_000_000: raise BundleError('Invalid media size')
        content = source.read_bytes()
        if frame.get('kind') != 'credits':
            try:
                validate_public_attribution(frame, content)
            except ValueError as error:
                raise BundleError(str(error)) from None
        digest = hashlib.sha256(content).hexdigest()
        if digest != frame['sha256']: raise BundleError('Media changed after approval')
        hashes.append(digest)
        media.append((source, content))
    if len(set(hashes)) != len(hashes): raise BundleError('Duplicate card in package')
    # Changing title/filename/expiry cannot cause an identical package to be resent.
    identity = hashlib.sha256(('executivesaudi:' + ':'.join(hashes)).encode()).hexdigest()
    selected = [media[i] for i in indices]
    if any(path.suffix.lower() == '.mp4' for path, _ in selected):
        raise BundleError('manual_video_requires_editorial_frame_review')
    return identity, str(data['title']), selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['check','validate','publish'], default='check', nargs='?')
    parser.add_argument('--manifest', default='')
    args = parser.parse_args()
    try:
        if args.mode == 'validate':
            identity, title, media = load_package(args.manifest)
            print(json.dumps({'status': 'validated_not_published', 'identity': identity,
                              'card_count': len(media)}, sort_keys=True))
            return
        client = BundleClient()
        client.check()
        print('API verified: Snapchat executivesaudi is connected.')
        if args.mode == 'publish':
            identity, title, media = load_package(args.manifest)
            check_predecessors(json.loads(Path(args.manifest).read_text()).get('predecessors', []))
            publish(client, GitHubJournal(identity), title, media)
    except (BundleError, KeyError, ValueError, OSError) as exc:
        print(str(exc) if isinstance(exc, BundleError) else 'Invalid package or state; no automatic retry')
        raise SystemExit(1) from None

if __name__ == '__main__': main()
