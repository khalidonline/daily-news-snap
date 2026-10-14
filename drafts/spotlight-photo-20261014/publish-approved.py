"""One-shot: post the owner-approved Crystal Pepsi and first-iPhone challenges.

Owner approval, 14 Oct 2026: «انشر البيبسي والآيفون» (Story + Spotlight, as
for Nokia/Samsung). Payloads mirror the owner's 10 Oct posts. A create is
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
ITEMS = [
    ('crystal-pepsi-approved.mp4', '60750393a2c43446949e1c3b0b33870cae4fd3857d9110c61acc3604afe5d176', 'نزل بالسوق — بيبسي الشفاف',
     'نزل بالسوق: بيبسي شفاف مثل الماء؟ اختَر قبل نهاية العد وأرسلها لخويك! #تحدي — الصورة: Mike Mozart، CC BY 2.0'),
    ('first-iphone-approved.mp4', '543e0b32f6ac30dadda63cbbc96c3237a73d62c3e2a7f45be41f26d6f4abb725', 'توقّع السعر — أول آيفون',
     'توقّع السعر: كم كان سعر أول آيفون في 2007؟ اختَر قبل نهاية العد وأرسلها لخويك! #تحدي'),
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
                (HERE / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
                return 1
            try:
                c.wait(post_id)
                status = c.call('/post/' + urllib.parse.quote(post_id, safe='')).get('status')
            except Exception as exc:
                status = f'unconfirmed: {exc}'
            print(kind, status, flush=True)
            receipt.append({'kind': kind, 'title': label, 'post_id': post_id, 'status': status})
    (HERE / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    return 0 if all(r['status'] == 'POSTED' for r in receipt) else 1


if __name__ == '__main__':
    sys.exit(main())
