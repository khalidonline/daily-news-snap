"""Read-only: print the Snapchat payload shape of given posts (no media URLs)."""
import json, os, sys
from publishing_v2.bundle_api import BundleClient

c = BundleClient()
for pid in (os.environ.get('POST_IDS') or '').split():
    p = c.call(f'/post/{pid}')
    snap = (p.get('data') or {}).get('SNAPCHAT') or {}
    print(pid, json.dumps({'title': p.get('title'), 'status': p.get('status'),
                           'top_keys': sorted(p), 'socialAccountTypes': p.get('socialAccountTypes'),
                           'snapchat': {k: v for k, v in snap.items() if k != 'uploadIds'}},
                          ensure_ascii=False))
