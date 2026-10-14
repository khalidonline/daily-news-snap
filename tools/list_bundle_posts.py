"""Read-only: list the account's bundle.social posts from the last N days.

Prints only post metadata (id, dates, status, Snapchat placement type, title).
Never creates, edits or deletes anything.
"""
from datetime import datetime, timedelta, timezone
import json
import os
import sys
import urllib.parse

from publishing_v2.bundle_api import BundleClient, HTTPFailure

DAYS = int(os.environ.get('DAYS') or 7)


def items_of(page):
    if isinstance(page, list):
        return page
    for key in ('items', 'data', 'posts', 'results'):
        if isinstance(page.get(key), list):
            return page[key]
    print('unknown response keys:', sorted(page))
    return []


def when(post):
    for key in ('postedDate', 'postDate', 'createdAt'):
        value = post.get(key)
        if value:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
    return None


def main():
    client = BundleClient()
    client.check()
    since = datetime.now(timezone.utc) - timedelta(days=DAYS)
    rows, offset = [], 0
    while True:
        query = urllib.parse.urlencode({'teamId': client.team, 'limit': 100, 'offset': offset,
                                        'orderBy': 'postDate', 'order': 'DESC'})
        try:
            page = client.call('/post?' + query)
        except HTTPFailure as exc:
            print('list request failed: HTTP', exc.code)
            return 1
        batch = items_of(page)
        rows += batch
        oldest = min((when(p) for p in batch if when(p)), default=None)
        if len(batch) < 100 or (oldest and oldest < since) or offset > 2000:
            break
        offset += 100
    recent = [p for p in rows if (when(p) or since) >= since]
    recent.sort(key=lambda p: when(p) or since)
    counts = {}
    print(f'posts since {since:%Y-%m-%d %H:%M} UTC: {len(recent)} (fetched {len(rows)})')
    for p in recent:
        snap = ((p.get('data') or {}).get('SNAPCHAT') or {})
        kind = snap.get('type') or '?'
        counts[kind] = counts.get(kind, 0) + 1
        ksa = when(p).astimezone(timezone(timedelta(hours=3))) if when(p) else None
        print(json.dumps({'riyadh': f'{ksa:%Y-%m-%d %H:%M}' if ksa else None,
                          'type': kind, 'status': p.get('status'),
                          'title': (p.get('title') or '')[:100], 'id': p.get('id'),
                          'uploads': len(snap.get('uploadIds') or [])}, ensure_ascii=False))
    print('counts by Snapchat type:', json.dumps(counts))
    return 0


if __name__ == '__main__':
    sys.exit(main())
