"""One-shot: post the owner-approved Nokia/Samsung challenge as a Story and on Spotlight.

Owner approval, 14 Oct 2026: «تمام انشر في القصه العامه ومنصة الأضواء ايضا».
Payload shapes copied from the owner's own 10 Oct posts (Story 285c5ffe,
Spotlight 65096cfc). A create is never retried: an ambiguous result is
printed for manual reconciliation, so a rerun cannot double-post.
"""
from datetime import datetime, timezone
import hashlib
import json
import sys
import urllib.parse
from pathlib import Path

from publishing_v2.bundle_api import BundleClient

HERE = Path(__file__).parent
MEDIA = HERE / 'nokia-samsung-approved.mp4'
SHA256 = 'd02bd266bf28500c2c3ee69997bbf4343a27a247a0bbc42b63ca650b1de20670'
STAMP = '20261014'
POSTS = [
    ('STORY', f'من بدأ أول — نوكيا وسامسونج — القصة العامة {STAMP}',
     {'type': 'STORY', 'storyDuration': 'ONE_WEEK'}),
    ('SPOTLIGHT', f'من بدأ أول — نوكيا وسامسونج — الأضواء {STAMP}',
     {'type': 'SPOTLIGHT', 'locale': 'ar_SA',
      'description': 'من بدأ أول: نوكيا أو سامسونج؟ اختَر قبل نهاية العد وأرسلها لخويك! #تحدي'}),
]


def main():
    data = MEDIA.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit('media differs from the approved file; not posting')
    c = BundleClient()
    c.check()
    c.ensure_capacity(len(POSTS))
    receipt = []
    for kind, title, snap in POSTS:
        upload = c.upload((MEDIA, data))
        payload = {'teamId': c.team, 'title': title[:100],
                   'postDate': datetime.now(timezone.utc).isoformat(), 'status': 'SCHEDULED',
                   'socialAccountTypes': ['SNAPCHAT'],
                   'data': {'SNAPCHAT': dict(snap, uploadIds=[upload])}}
        result = c.call('/post', 'POST', json.dumps(payload).encode())
        post_id = result.get('id')
        print(kind, 'created', post_id, flush=True)
        if not post_id:
            print('ambiguous create; stop and reconcile in the bundle.social dashboard')
            return 1
        try:
            c.wait(post_id)
            row = c.call('/post/' + urllib.parse.quote(post_id, safe=''))
            status = row.get('status')
        except Exception as exc:
            status = f'unconfirmed: {exc}'
        print(kind, status, flush=True)
        receipt.append({'kind': kind, 'title': title, 'post_id': post_id, 'status': status})
    (HERE / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    return 0 if all(r['status'] == 'POSTED' for r in receipt) else 1


if __name__ == '__main__':
    sys.exit(main())
