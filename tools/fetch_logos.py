"""Fetch candidate wordmark PNGs from Wikimedia Commons (read-only GETs)."""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import news_bot

OUT = Path('reference/logos')
WANTED = {
    'cocacola': ['Coca-Cola logo.svg', 'Coca-Cola wordmark.svg'],
    'pepsi': ['Pepsi logo 2023.svg', 'Pepsi 2023.svg', 'Pepsi logo 2014.svg', 'Pepsi logo.svg', 'Pepsi wordmark.svg'],
    'toyota': ['Toyota carlogo.svg', 'Toyota logo.svg'],
    'honda': ['Honda.svg', 'Honda logo.svg'],
}


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': news_bot.PUBLIC_API_UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, titles in WANTED.items():
        for title in titles:
            q = urllib.parse.urlencode({'action': 'query', 'titles': 'File:' + title, 'prop': 'imageinfo',
                                        'iiprop': 'url|extmetadata', 'iiurlwidth': 1200, 'format': 'json'})
            try:
                page = next(iter(json.loads(get('https://commons.wikimedia.org/w/api.php?' + q))['query']['pages'].values()))
            except Exception as exc:
                print(slug, title, 'lookup failed', type(exc).__name__)
                continue
            info = (page.get('imageinfo') or [{}])[0]
            if not info.get('thumburl'):
                print(slug, title, 'missing')
                continue
            meta = info.get('extmetadata') or {}
            lic = (meta.get('LicenseShortName') or {}).get('value')
            name = OUT / f"{slug}-{title.replace(' ', '_').rsplit('.', 1)[0]}.png"
            name.write_bytes(get(info['thumburl']))
            print(slug, title, 'license:', lic, 'saved', name, name.stat().st_size)
    return 0


if __name__ == '__main__':
    sys.exit(main())
