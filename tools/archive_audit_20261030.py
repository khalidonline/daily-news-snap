"""Owner-requested read-only archive inventory; no provider mutations."""
import json
from urllib.parse import urlencode
from publishing_v2.bundle_api import BundleClient, BundleError

client = BundleClient()
client.check()
offset = 0
rows = []
while True:
    page = client.call('/post/?' + urlencode({'teamId': client.team, 'offset': offset, 'limit': 100}))
    items, total = page.get('items'), page.get('total')
    if not isinstance(items, list) or not isinstance(total, int):
        raise BundleError('Incomplete inventory response')
    for item in items:
        if item.get('teamId') != client.team:
            raise BundleError('Wrong account in inventory')
        snap = (item.get('data') or {}).get('SNAPCHAT') or {}
        date = item.get('postDate') or item.get('createdAt') or ''
        if snap.get('type') == 'SAVED_STORY' or date >= '2026-10-25':
            rows.append({'id': item.get('id'), 'type': snap.get('type'), 'title': item.get('title'), 'saved_title': snap.get('title'), 'date': date, 'status': item.get('status'), 'deleted': bool(item.get('deletedAt')), 'uploads': snap.get('uploadIds')})
    offset += len(items)
    if offset >= total:
        break
    if not items or offset > 10000:
        raise BundleError('Incomplete inventory')
for row in sorted(rows, key=lambda r: r['date']):
    print(json.dumps(row, ensure_ascii=False))
print('COMPLETE_READ_ONLY_INVENTORY', total)
