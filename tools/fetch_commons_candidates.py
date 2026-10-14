"""Read-only: save Commons search candidates (thumb + licence/author) for review."""
import json, re, sys, urllib.parse, urllib.request
from pathlib import Path
import news_bot

OUT = Path('reference/candidates')
QUERIES = {
    'edge': ['Edge of the World Riyadh', 'Jebel Fihrayn', 'Tuwaiq escarpment Edge of the World'],
}


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': news_bot.PUBLIC_API_UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def strip(html):
    return re.sub(r'<[^>]+>', '', html or '').strip()[:120]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    for slug, queries in QUERIES.items():
        n = 0
        seen = set()
        for q in queries:
            params = {'action': 'query', 'generator': 'search', 'gsrsearch': q, 'gsrnamespace': 6,
                      'gsrlimit': 8, 'prop': 'imageinfo', 'iiprop': 'url|extmetadata|size|mime',
                      'iiurlwidth': 1200, 'format': 'json'}
            pages = json.loads(get('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode(params)))
            for page in sorted((pages.get('query') or {}).get('pages', {}).values(), key=lambda p: p.get('index', 0)):
                info = (page.get('imageinfo') or [{}])[0]
                if page['title'] in seen or info.get('mime') not in ('image/jpeg', 'image/png') or not info.get('thumburl'):
                    continue
                seen.add(page['title'])
                m = info.get('extmetadata') or {}
                n += 1
                name = f'{slug}-{n:02d}.jpg'
                try:
                    (OUT / name).write_bytes(get(info['thumburl']))
                except Exception as exc:
                    print('download failed', page['title'], type(exc).__name__)
                    continue
                meta[name] = {'title': page['title'], 'license': strip((m.get('LicenseShortName') or {}).get('value')),
                              'artist': strip((m.get('Artist') or {}).get('value')),
                              'size': [info.get('width'), info.get('height')],
                              'page': info.get('descriptionurl')}
                print(name, json.dumps(meta[name], ensure_ascii=False))
                if n >= 10:
                    break
    (OUT / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
