"""One-shot: post the owner-approved Crystal Pepsi and first-iPhone challenges.

Owner approvals, 14 Oct 2026: Pepsi/iPhone, Haramain, then «انشر» for Wadi
Disah (Story + Spotlight, as for Nokia/Samsung). Payloads mirror the owner's 10 Oct posts. A create is
never retried, so a rerun cannot double-post; the media hash must match.
"""
from datetime import datetime, timezone
import hashlib
import json
import sys
import urllib.parse
from pathlib import Path

from publishing_v2.bundle_api import BundleClient

HERE = Path(__file__).parent
STAMP = '20261014'
RECEIPT = 'receipt-disah.json'
ITEMS = [
    ('disah-approved.mp4', 'd7dab15e3bf1011c50b790d6e78a511fdc4203e1c08d9dac4f6ec3c1e61cb29a', 'توقّع المكان — وادي الديسة',
     'توقّع المكان: أريزونا ولا تبوك؟ اختَر قبل نهاية العد وأرسلها لخويك! #تحدي'),
]


def main():
    media = []
    for name, sha, title, description in ITEMS:
        data = (HERE / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            raise SystemExit(f'{name} differs from the approved file; not posting')
        media.append((HERE / name, data, title, description))
    c = BundleClient()
    c.check()
    c.ensure_capacity(2 * len(media))
    receipt = []
    for path, data, title, description in media:
        for kind, snap in (('STORY', {'type': 'STORY', 'storyDuration': 'ONE_WEEK'}),
                           ('SPOTLIGHT', {'type': 'SPOTLIGHT', 'locale': 'ar_SA',
                                          'description': description})):
            label = f"{title} — {'القصة العامة' if kind == 'STORY' else 'الأضواء'} {STAMP}"
            upload = c.upload((path, data))
            payload = {'teamId': c.team, 'title': label[:100],
                       'postDate': datetime.now(timezone.utc).isoformat(), 'status': 'SCHEDULED',
                       'socialAccountTypes': ['SNAPCHAT'],
                       'data': {'SNAPCHAT': dict(snap, uploadIds=[upload])}}
            post_id = c.call('/post', 'POST', json.dumps(payload).encode()).get('id')
            print(kind, label, 'created', post_id, flush=True)
            if not post_id:
                print('ambiguous create; stop and reconcile in the bundle.social dashboard')
                (HERE / RECEIPT).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
                return 1
            try:
                c.wait(post_id)
                status = c.call('/post/' + urllib.parse.quote(post_id, safe='')).get('status')
            except Exception as exc:
                status = f'unconfirmed: {exc}'
            print(kind, status, flush=True)
            receipt.append({'kind': kind, 'title': label, 'post_id': post_id, 'status': status})
    (HERE / RECEIPT).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    return 0 if all(r['status'] == 'POSTED' for r in receipt) else 1


if __name__ == '__main__':
    sys.exit(main())
