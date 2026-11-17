"""Shared exact-byte, two-destination challenge delivery. No production path.

Default validation is offline. Publication requires explicit action, an expected
video hash, the manifest's scheduled lower bound and all existing shared gates.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import urllib.parse

from .bundle_api import BundleClient, BundleError, GitHubJournal, load_package, publish
from .design_contract import validate_design
from .readability import require_for_new_delivery

DESTINATIONS = ('STORY', 'SPOTLIGHT')


def package_path(package):
    if not isinstance(package, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,80}', package):
        raise BundleError('Invalid challenge package')
    return Path('approved') / package


MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_PARTS = 128
MAX_PART_BYTES = 600_000


def read_archive_bytes(package, spec, reader=None):
    """Verify every bounded part and the combined hash before archive parsing."""
    archive_path = package_path(package).with_suffix('.tar.xz').as_posix()
    if (not isinstance(spec, dict) or spec.get('path') != archive_path
            or not re.fullmatch('[0-9a-f]{64}', str(spec.get('sha256', '')))):
        raise BundleError('Invalid challenge archive description')
    def local_read(relative, maximum):
        path = Path(relative)
        root = Path.cwd().resolve()
        if (path.is_symlink() or path.parent.is_symlink()
                or not path.resolve().is_relative_to(root)):
            raise BundleError('Unsafe challenge archive file')
        with path.open('rb') as source:
            return source.read(maximum + 1)
    reader = reader or local_read
    try:
        if 'parts' in spec:
            parts = spec['parts']
            if not isinstance(parts, list) or not 1 <= len(parts) <= MAX_ARCHIVE_PARTS:
                raise BundleError('Invalid challenge archive part count')
            # Inspect the entire declared sequence before reading any part.
            for index, part in enumerate(parts):
                if (not isinstance(part, dict)
                        or part.get('path') != archive_path + f'.part-{index:03d}'
                        or not re.fullmatch('[0-9a-f]{64}', str(part.get('sha256', '')))):
                    raise BundleError('Invalid challenge archive part sequence or hash')
            chunks = []
            total = 0
            for part in parts:
                chunk = reader(part['path'], MAX_PART_BYTES)
                total += len(chunk)
                if (not 0 < len(chunk) <= MAX_PART_BYTES or total > MAX_ARCHIVE_BYTES
                        or hashlib.sha256(chunk).hexdigest() != part['sha256']):
                    raise BundleError('Challenge archive part differs or exceeds limit')
                chunks.append(chunk)
            raw = b''.join(chunks)
        else:
            raw = reader(archive_path, MAX_ARCHIVE_BYTES)
        if (not 0 < len(raw) <= MAX_ARCHIVE_BYTES
                or hashlib.sha256(raw).hexdigest() != spec['sha256']):
            raise BundleError('Challenge archive differs from manifest-bound bytes')
        return raw
    except (OSError, ValueError, TypeError):
        raise BundleError('Challenge archive media unavailable or invalid') from None


def restore_media(package):
    """Optional binary-only archive. Never restore approval/code from an archive."""
    folder = package_path(package)
    archive_path = folder.with_suffix('.tar.xz')
    try:
        manifest = json.loads((folder / 'manifest.json').read_text())
        spec = manifest.get('asset_archive')
        if spec is None and not archive_path.exists():
            return
        raw_archive = read_archive_bytes(package, spec)
    except (OSError, ValueError, TypeError):
        raise BundleError('Challenge archive manifest or media unavailable') from None
    root = Path.cwd().resolve()
    try:
        with tarfile.open(fileobj=io.BytesIO(raw_archive), mode='r:xz') as archive:
            members = archive.getmembers()
            if len(members) > 100 or sum(m.size for m in members) > 150_000_000:
                raise BundleError('Challenge archive exceeds bounded media size')
            targets = []
            for member in members:
                path = PurePosixPath(member.name)
                target = (root / member.name).resolve()
                if (path.is_absolute() or '..' in path.parts or '\\' in member.name
                        or not target.is_relative_to(root / folder)):
                    raise BundleError('Unsafe challenge archive path')
                if member.isdir():
                    continue
                if (not member.isfile() or member.mode & 0o111 or member.size <= 0
                        or path.suffix.lower() not in {'.mp4', '.m4a', '.png', '.jpg', '.jpeg'}
                        or member.name in targets):
                    raise BundleError('Challenge archive must contain media only')
                targets.append(member.name)
            # Validate the complete table first; install no partial unsafe archive.
            for member in members:
                if member.isdir():
                    continue
                target = root / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source:
                    raw = source.read()
                if len(raw) != member.size:
                    raise BundleError('Truncated challenge media')
                target.write_bytes(raw)
    except (OSError, tarfile.TarError) as exc:
        raise BundleError('Challenge media archive unavailable or invalid') from exc


def check_binding(data, media, expected):
    if (not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected)
            or len(media) != 1 or Path(media[0][0]).suffix.lower() != '.mp4'
            or hashlib.sha256(media[0][1]).hexdigest() != expected):
        raise BundleError('Exact expected video SHA256 required; no regeneration or fallback')
    if (data.get('format') != 'reviewed-challenge-video-v1'
            or data.get('content_type') != 'challenge'
            or data.get('approved_destinations') != list(DESTINATIONS)):
        raise BundleError('Explicit STORY and SPOTLIGHT challenge approval required')
    try:
        due = datetime.fromisoformat(data['not_before'].replace('Z', '+00:00'))
        expiry = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
        if due.tzinfo is None or expiry.tzinfo is None or due >= expiry:
            raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise BundleError('Valid timezone-aware not_before and expiry required') from None
    return due


def validate_package(package, expected):
    folder = package_path(package)
    restore_media(package)
    identity, title, media = load_package(str(folder / 'manifest.json'))
    data = media.snapshot
    check_binding(data, media, expected)
    try:
        report = json.loads((folder / 'design-review.json').read_text())
    except (OSError, ValueError):
        raise BundleError('Final challenge design review required') from None
    # Local/hash-bound validation only. Live revocation is additionally checked
    # by DeliveryReview and ApprovedMedia before every publication mutation.
    for destination in DESTINATIONS:
        validate_design(media, report, destination)
    return identity, title, media, data


class ChallengeClient(BundleClient):
    def __init__(self, digest, not_before):
        super().__init__()
        self.digest = digest
        self.not_before = not_before

    def call(self, path, method='GET', data=None, content_type='application/json'):
        if datetime.now(timezone.utc) < self.not_before:
            raise BundleError('Challenge is before scheduled not_before; no provider call')
        if path == '/post' and method == 'POST':
            payload = json.loads(data)
            snap = payload['data']['SNAPCHAT']
            if snap.get('type') not in DESTINATIONS:
                raise BundleError('Unsupported challenge destination')
            payload['referenceKey'] = 'reviewed-challenge-' + self.digest + '-' + snap['type']
            if snap['type'] == 'SPOTLIGHT':
                snap['skipSaveToProfile'] = True
            data = json.dumps(payload).encode()
        return super().call(path, method, data, content_type)


class BoundJournal:
    def __init__(self, journal, package, placement, digest, not_before):
        self.journal, self.package, self.placement = journal, package, placement
        self.digest, self.not_before = digest, not_before

    def read(self):
        state = self.journal.read()
        for key, row in state.items():
            if key.isdigit() and isinstance(row, dict):
                if row.get('media_sha256', self.digest) != self.digest:
                    raise BundleError('Existing challenge receipt hash mismatch')
                if row.get('placement', 'STORY') != self.placement:
                    raise BundleError('Existing challenge receipt destination mismatch')
        return state

    def save(self, state):
        for key, row in state.items():
            if key.isdigit() and isinstance(row, dict):
                row.update(media_sha256=self.digest, package=self.package,
                           reference_key='reviewed-challenge-' + self.digest + '-' + self.placement,
                           not_before=self.not_before)
        self.journal.save(state)


def verify_receipt(client, row, placement, digest):
    remote = client.call('/post/' + urllib.parse.quote(row['post_id'], safe=''))
    snap = (remote.get('externalData') or {}).get('SNAPCHAT') or {}
    if (remote.get('id') != row['post_id'] or remote.get('teamId') != client.team
            or remote.get('deletedAt') or remote.get('status') != 'POSTED'
            or snap.get('status') != 'PUBLISHED' or snap.get('type') != placement
            or snap.get('sourceUploadIds') != [row.get('upload_id')]):
        raise BundleError('Unconfirmed challenge provider receipt: ' + placement)
    return {'post_id': row['post_id'], 'media_sha256': digest,
            'status': 'POSTED', 'snapchat_status': 'PUBLISHED', 'external_data': snap}


def deliver(client, journals, title, media, digest):
    states = {destination: journals[destination].read() for destination in DESTINATIONS}
    # Inspect BOTH destinations before any new upload. Unknown create intent in
    # either one blocks fresh sends; no retry loop or replacement identity.
    for state in states.values():
        if state.get('_group'):
            raise BundleError('Grouped challenge receipt needs manual reconciliation')
        if any(row is not None and not row.get('post_id') for row in [state.get('1')]):
            raise BundleError('Uncertain previous challenge create; reconcile first')
    # Reconcile known operations before creating another destination.
    ordered = sorted(DESTINATIONS, key=lambda dest: states[dest].get('1') is None)
    results = {}
    for destination in ordered:
        journal = journals[destination]
        require_for_new_delivery(media.path, media, journal.read())
        publish(client, journal, title, media, placement=destination)
        results[destination] = verify_receipt(client, journal.read()['1'], destination, digest)
    return results


def run(package, expected, *, action='validate', now=None):
    if action not in {'validate', 'publish'}:
        raise BundleError('Explicit validate or publish action required')
    identity, title, media, data = validate_package(package, expected)
    if action == 'validate':
        from .challenge_visual_review import validate_challenge_images
        validate_challenge_images(media)
        return {'status': 'VALIDATED_NOT_PUBLISHED', 'package': package,
                'identity': identity, 'sha256': expected, 'not_before': data['not_before'],
                'destinations': list(DESTINATIONS)}
    due = datetime.fromisoformat(data['not_before'].replace('Z', '+00:00'))
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now < due:
        raise BundleError('Challenge is before scheduled not_before; no provider call')
    if os.environ.get('POST_TO_SNAPCHAT') != '1' or os.environ.get('DRY_RUN') != '0':
        raise BundleError('Explicit publication environment required')
    client = ChallengeClient(expected, due)
    journals = {}
    for destination in DESTINATIONS:
        key = identity if destination == 'STORY' else hashlib.sha256((identity + ':SPOTLIGHT').encode()).hexdigest()
        journals[destination] = BoundJournal(GitHubJournal(key), package, destination, expected, data['not_before'])
    client.check()
    receipts = deliver(client, journals, title, media, expected)
    return {'status': 'POSTED', 'package': package, 'sha256': expected, 'destinations': receipts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--expected-video-sha256', required=True)
    parser.add_argument('--action', choices=('validate', 'publish'), default='validate')
    args = parser.parse_args(argv)
    print(json.dumps(run(args.package, args.expected_video_sha256, action=args.action), ensure_ascii=False))


if __name__ == '__main__':
    main()
