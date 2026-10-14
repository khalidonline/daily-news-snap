"""Read-only: download the media of given bundle.social posts for design reference.

GET requests only; saves files under reference/spotlight/ and prints the
post fields that point at media so a changed response shape is visible.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

from publishing_v2.bundle_api import BundleClient

OUT = Path('reference/spotlight')
IDS = (os.environ.get('POST_IDS') or '').split()


def urls(node, path=''):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from urls(v, f'{path}.{k}')
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from urls(v, f'{path}[{i}]')
    elif isinstance(node, str) and node.startswith('http'):
        yield path, node


def main():
    client = BundleClient()
    OUT.mkdir(parents=True, exist_ok=True)
    for pid in IDS:
        post = client.call(f'/post/{pid}')
        snap = (post.get('data') or {}).get('SNAPCHAT') or {}
        print(pid, post.get('title'), snap.get('type'), 'uploadIds', snap.get('uploadIds'))
        found = list(urls(post))
        for upload in snap.get('uploadIds') or []:
            try:
                found += [(f'upload:{upload}{p}', u) for p, u in urls(client.call(f'/upload/{upload}'))]
            except Exception as exc:  # report and continue, never retry writes
                print('upload lookup failed', upload, type(exc).__name__, getattr(exc, 'code', ''))
        for n, (where, url) in enumerate(found):
            print('  url at', where)
            name = OUT / f'{pid[:8]}-{n}{Path(url.split("?")[0]).suffix or ".bin"}'
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'ExecutiveSaudiPublisher/1.0'})
                with urllib.request.urlopen(req, timeout=60) as r:
                    name.write_bytes(r.read())
                print('  saved', name, name.stat().st_size)
            except Exception as exc:
                print('  download failed', type(exc).__name__)
    return 0


if __name__ == '__main__':
    sys.exit(main())
