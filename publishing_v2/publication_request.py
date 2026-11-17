"""Route one explicit main-push request. No production or provider calls.

Information requests retain their existing resolver. Reviewed challenges bind
both the exact video and its committed review/archive, with an explicit action.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from . import information_request
from .deliver_challenge import read_archive_bytes
from .bundle_api import BundleError

CHALLENGE_REQUEST = '.github/challenge-publish-request.json'
INFORMATION_REQUEST = information_request.REQUEST_PATH


def date(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Timezone-aware request time required') from None


def push_changes(root, event):
    if (event.get('ref') != 'refs/heads/main'
            or event.get('repository', {}).get('full_name') != 'khalidonline/daily-news-snap'
            or event.get('deleted') is not False or event.get('forced') is not False):
        raise ValueError('Expected non-forced main push')
    before, after = event.get('before', ''), event.get('after', '')
    if any(not isinstance(v, str) or not re.fullmatch('[0-9a-f]{40}', v) or v == '0' * 40 for v in (before, after)):
        raise ValueError('Invalid push range')
    if information_request.git(root, 'rev-parse', 'HEAD').decode().strip() != after:
        raise ValueError('Checkout differs from push')
    subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', before, after],
                   check=True, capture_output=True, timeout=30)
    return set(information_request.git(root, 'diff', '--name-only', '-z', before, after).decode().split('\0'))


def committed_bytes(root, relative, commit, maximum=None):
    path = information_request.checked_path(root, relative)
    if maximum is not None:
        committed_size = int(information_request.git(root, 'cat-file', '-s', commit + ':' + relative))
        if not 0 < path.stat().st_size <= maximum or not 0 < committed_size <= maximum:
            raise ValueError('Challenge archive part exceeds bounded size')
    local = path.read_bytes()
    if local != information_request.git(root, 'show', commit + ':' + relative):
        raise ValueError('Request or package differs from event commit')
    return local


def resolve_challenge(root, event, now):
    after = event['after']
    request = json.loads(committed_bytes(root, CHALLENGE_REQUEST, after))
    if not isinstance(request, dict) or request.get('version') != 1 or request.get('action') not in ('validate', 'publish'):
        raise ValueError('Explicit challenge validate or publish action required')
    package = request.get('package')
    digest = request.get('expected_video_sha256')
    if not isinstance(package, str) or not re.fullmatch('[a-z0-9][a-z0-9-]{2,80}', package):
        raise ValueError('Invalid challenge package')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Exact expected video SHA256 required')
    folder = 'approved/' + package
    inputs = [('manifest_sha256', folder + '/manifest.json'),
              ('design_review_sha256', folder + '/design-review.json'),
              ('source_manifest_sha256', folder + '/source-approval.json')]
    contents = {}
    for field, relative in inputs:
        raw = committed_bytes(root, relative, after)
        if hashlib.sha256(raw).hexdigest() != request.get(field):
            raise ValueError('Request-bound challenge bytes changed: ' + field)
        contents[field] = raw
    manifest = json.loads(contents['manifest_sha256'])
    # Legacy whole archives remain supported. A declared parts list always
    # takes priority, even when an old whole file is still in the checkout.
    spec = manifest.get('asset_archive', {'path': folder + '.tar.xz',
                                         'sha256': request.get('media_archive_sha256')})
    if not isinstance(spec, dict) or spec.get('sha256') != request.get('media_archive_sha256'):
        raise ValueError('Request differs from combined challenge archive hash')
    try:
        read_archive_bytes(package, spec,
            reader=lambda relative, maximum: committed_bytes(root, relative, after, maximum))
    except BundleError as exc:
        raise ValueError(str(exc)) from exc
    if (manifest.get('format') != 'reviewed-challenge-video-v1'
            or manifest.get('content_type') != 'challenge' or manifest.get('approved') is not True
            or manifest.get('approved_destinations') != ['STORY', 'SPOTLIGHT']
            or len(manifest.get('media', [])) != 1
            or manifest['media'][0].get('sha256') != digest
            or manifest.get('not_before') != request.get('not_before')):
        raise ValueError('Request differs from approved challenge manifest')
    due, expiry = date(request.get('not_before')), date(manifest.get('expires_at'))
    if now.tzinfo is None or due >= expiry or now >= expiry:
        raise ValueError('Challenge request window invalid or expired')
    if request['action'] == 'publish' and now < due:
        raise ValueError('Challenge publish request is before scheduled not_before')
    return {'mode': 'reviewed-challenge', 'package': package,
            'challenge_action': request['action'], 'expected_video_sha256': digest,
            'not_before': request['not_before']}


def resolve_push(root, event, now):
    root = Path(root).resolve()
    changed = push_changes(root, event)
    relevant = changed.intersection({INFORMATION_REQUEST, CHALLENGE_REQUEST})
    if len(relevant) != 1:
        raise ValueError('Exactly one publication request type may change per push')
    if INFORMATION_REQUEST in relevant:
        package = information_request.resolve_push(root, event, now)
        return {'mode': 'prepared-information', 'package': package.name}
    return resolve_challenge(root, event, now)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['resolve-push'])
    parser.add_argument('--event', required=True)
    args = parser.parse_args(argv)
    outputs = resolve_push(Path.cwd(), json.loads(Path(args.event).read_text()), datetime.now(timezone.utc))
    for key, value in outputs.items():
        if '\n' in value or '\r' in value:
            raise ValueError('Unsafe workflow output')
        print(key + '=' + value)


if __name__ == '__main__':
    main()
