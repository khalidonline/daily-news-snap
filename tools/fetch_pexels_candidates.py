"""Read-only: save Pexels search candidates (photo + photographer + alt) for review."""
import json, os, sys, urllib.parse, urllib.request
from pathlib import Path

OUT = Path('reference/pexels')
QUERIES = {
    'neom': 'NEOM Saudi Arabia',
    'asir': 'Asir Saudi Arabia green',
    'fog': 'Abha fog',
    'island': 'Saudi Arabia island turquoise',
    'snowksa': 'snow Saudi Arabia',
    'balad': 'Al Balad Jeddah',
    'ahsa': 'Al Ahsa',
    'tanomah': 'Tanomah',
}


def get(url, headers=None):
    req = urllib.request.Request(url, headers=dict({'User-Agent': 'daily-news-snap/1.0'}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def main():
    key = os.environ['PEXELS_API_KEY']
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    for slug, q in QUERIES.items():
        res = json.loads(get('https://api.pexels.com/v1/search?' + urllib.parse.urlencode(
            {'query': q, 'per_page': 8, 'orientation': 'landscape'}), {'Authorization': key}))
        for n, ph in enumerate(res.get('photos', []), 1):
            name = f'{slug}-{n:02d}.jpg'
            try:
                (OUT / name).write_bytes(get(ph['src']['large']))
            except Exception as exc:
                print('download failed', name, type(exc).__name__)
                continue
            meta[name] = {'query': q, 'alt': ph.get('alt'), 'photographer': ph.get('photographer'),
                          'url': ph.get('url'), 'id': ph.get('id'), 'size': [ph.get('width'), ph.get('height')]}
            print(name, json.dumps(meta[name], ensure_ascii=False))
    (OUT / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
