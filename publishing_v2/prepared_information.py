"""Offline integrity preparation, never publication authorization.

Run from the repository root. The record cannot replace final editorial,
design, approval, account, quota or idempotency checks.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_path(path):
    root = Path.cwd().resolve()
    path = Path(path)
    if '..' in path.parts:
        raise ValueError('Traversal is not a package path')
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('Path escapes repository')
    return resolved


def package_path(package_dir):
    path = safe_path(package_dir)
    relative = path.relative_to(Path.cwd().resolve())
    if (len(relative.parts) != 2 or relative.parts[0] != 'approved'
            or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,80}', relative.name)):
        raise ValueError('Expected approved/<package>')
    return path


def read_json(path):
    value = json.loads(safe_path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError('Expected JSON object')
    return value


def content_digest(value, archive=False):
    value = dict(value)
    value.pop('approved', None)
    if archive:
        for name in ('manifest_sha256', 'owner_authorization'):
            value.pop(name, None)
    else:
        review = dict(value.get('owner_review', {}))
        for name in ('reference', 'reviewed_at'):
            review.pop(name, None)
        value.pop('owner_review', None)
        if review:
            value['owner_review'] = review
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def snapshot(package_dir):
    p = package_path(package_dir)
    data = read_json(p / 'manifest.json')
    if (data.get('account') != 'executivesaudi'
            or data.get('content_type') != 'information'
            or data.get('approved_destinations') != ['STORY', 'SAVED_STORY']
            or data.get('story_duration') != 'ONE_WEEK'):
        raise ValueError('Prepared route requires information Story and Saved Story')
    frames = data.get('media')
    if not isinstance(frames, list) or not 1 <= len(frames) <= 2:
        raise ValueError('Expected one or two cards')
    assets = {}
    for frame in frames:
        for row in [frame] + frame.get('source_assets', []):
            supplied = Path(row['path'])
            if supplied.is_absolute():
                raise ValueError('Asset path must be repository-relative')
            path = safe_path(supplied)
            if path.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
                raise ValueError('Information images only')
            actual = digest(path.read_bytes())
            if actual != row.get('sha256'):
                raise ValueError('Asset differs from recorded hash')
            assets[supplied.as_posix()] = actual
    return {
        'version': 1, 'status': 'PREPARED_NOT_AUTHORIZED',
        'package': p.relative_to(Path.cwd().resolve()).as_posix(),
        'manifest_content_sha256': content_digest(data),
        'archive_content_sha256': content_digest(read_json(p/'archive-approval.json'), archive=True),
        'settings_sha256': digest(safe_path('publishing_v2/design-settings.json').read_bytes()),
        'review_sha256': digest(safe_path(p/'design-review.json').read_bytes()),
        'assets': assets,
    }


def prepare(package_dir):
    start = time.monotonic()
    record = snapshot(package_dir)
    record['preparation_seconds'] = round(time.monotonic() - start, 3)
    output = safe_path(package_path(package_dir)/'prepared.json')
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    return record


def prepare_preview(package_dir):
    """Finish offline layout/archive preparation BEFORE owner review.

    This does not grant approval or replace live account/quota/reconciliation.
    Existing prepared packages keep their integrity-only verification semantics.
    """
    from .design_contract import validate_design
    from .bundle_api import BundleError
    p = package_path(package_dir)
    snapshot(p)  # Paths and all asset hashes before reading media.
    data = read_json(p/'manifest.json')
    archive = read_json(p/'archive-approval.json')
    if data.get('approved') is not False or archive.get('approved') is not False:
        raise ValueError('Preview preparation requires both approvals false')
    if (archive.get('account') != data['account']
            or archive.get('manifest') != (p/'manifest.json').relative_to(Path.cwd()).as_posix()
            or not archive.get('empty_profile_confirmation')
            or archive.get('expires_at') != data.get('expires_at')
            or not archive.get('identity')
            or archive.get('public_indices') != list(range(1,len(data['media'])+1))):
        raise ValueError('Complete draft archive fields before preview')
    frames = data['media']
    review = data.get('owner_review', {})
    if (review.get('approved_media_sha256') != [f['sha256'] for f in frames]
            or review.get('approved_source_sha256') != [s['sha256'] for f in frames for s in f.get('source_assets',[])]):
        raise ValueError('Precompute exact review hashes before preview; approval stays false')
    media = [(f['path'],safe_path(f['path']).read_bytes()) for f in frames]
    report = read_json(p/'design-review.json')
    for placement in data['approved_destinations']:
        try:
            validate_design(media,report,placement)
        except BundleError as exc:
            raise ValueError(str(exc)) from exc
    return prepare(p)


def verify_prepared(package_dir):
    record = read_json(package_path(package_dir)/'prepared.json')
    expected = dict(record)
    expected.pop('preparation_seconds', None)
    if expected != snapshot(package_dir):
        raise ValueError('Prepared package changed; review and prepare again')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'prepare-preview', 'verify'])
    parser.add_argument('--package', required=True)
    args = parser.parse_args()
    result = {'prepare':prepare,'prepare-preview':prepare_preview,'verify':verify_prepared}[args.mode](Path('approved')/args.package)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
