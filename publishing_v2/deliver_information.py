"""Deliver exact prepared information through existing guarded publishers.

No rendering, generation, alternate API client, or receipt replacement here.
Re-run the same package to reconcile existing operations, never a new identity.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from .prepared_information import package_path, read_json, verify_prepared
from .saved_story_api import validate_archive_authorization


class DeliveryFailure(RuntimeError):
    def __init__(self, result):
        self.result = result
        super().__init__('Delivery unconfirmed; retain package and reconcile receipts')


def deliver(package_dir):
    start = time.monotonic()
    p = package_path(package_dir)
    verify_prepared(p)
    manifest = (p/'manifest.json').relative_to(Path.cwd().resolve()).as_posix()
    archive = (p/'archive-approval.json').relative_to(Path.cwd().resolve()).as_posix()
    approval = read_json(p/'archive-approval.json')
    if approval.get('manifest') != manifest:
        raise ValueError('Archive must refer to this exact package manifest')
    identity, _, _, _ = validate_archive_authorization(approval)
    subprocess.run([sys.executable, '-m', 'publishing_v2.bundle_api', 'validate',
                    '--manifest', manifest], check=True)
    result = {'identity': identity, 'STORY': 'NOT_STARTED', 'SAVED_STORY': 'NOT_STARTED',
              'seconds': {'preflight': round(time.monotonic()-start, 3)}}
    for destination, phase, args in [
        ('STORY', 'story', ['publishing_v2.bundle_api', 'publish', '--manifest', manifest]),
        ('SAVED_STORY', 'archive', ['publishing_v2.saved_story_api', '--approval', archive]),
    ]:
        phase_start = time.monotonic()
        result[destination] = 'UNCONFIRMED_CHECK_RECEIPTS'
        try:
            subprocess.run([sys.executable, '-m', *args], check=True)
        except (subprocess.SubprocessError, OSError) as exc:
            result['seconds'][phase] = round(time.monotonic()-phase_start, 3)
            result['seconds']['total'] = round(time.monotonic()-start, 3)
            raise DeliveryFailure(result) from exc
        result[destination] = 'CONFIRMED_BY_PUBLISHER'
        result['seconds'][phase] = round(time.monotonic()-phase_start, 3)
    result['seconds']['total'] = round(time.monotonic()-start, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    args = parser.parse_args()
    try:
        result = deliver(Path('approved')/args.package)
    except DeliveryFailure as exc:
        print(json.dumps(exc.result, ensure_ascii=False), flush=True)
        raise SystemExit(1)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
