"""Discover first-party media albums; availability does not grant publication rights.

Profiles bind subjects, newsroom and asset hosts. Model-generated URLs and ordinary
page decorations never enter this catalog. CEER is the first verified profile.
"""
import hashlib
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from .public_images import get_bytes, ImageSourceError

PROFILES = ({
    'aliases': {'ceer', 'ceer motors', 'ceer exobot', 'exobot', 'سير', 'إكزوبوت'},
    'newsroom': 'https://ceermotors.com/news/',
    'asset_host': 'assets.ceermotors.com',
    'terms': 'https://ceermotors.com/terms-of-use/',
    'credit': 'CEER',
},)


class NewsLinks(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs).get('href', ''))


def album_assets(html):
    """Decode public server-rendered album JSON without executing site scripts."""
    chunks = []
    for match in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>', html, re.S):
        try:
            value = json.loads(match[1])
            if len(value) == 2 and value[0] == 1 and isinstance(value[1], str):
                chunks.append(value[1])
        except (ValueError, TypeError):
            continue
    data = ''.join(chunks)
    for match in re.finditer(r'"mediaAssets"\s*:\s*', data):
        try:
            album, _ = json.JSONDecoder().raw_decode(data[match.end():])
            if isinstance(album, dict) and isinstance(album.get('assets'), list):
                yield from album['assets'][:100]
        except ValueError:
            continue


def search_official(subject, *, limit=50, fetch=None):
    profile = next((p for p in PROFILES if isinstance(subject, str)
                    and subject.casefold().strip() in p['aliases']), None)
    if profile is None:
        return []
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('invalid_official_image_limit')
    fetch = fetch or get_bytes
    root = profile['newsroom']
    index = fetch(root, limit=2 * 1024 * 1024).decode('utf-8', errors='replace')
    parser = NewsLinks(); parser.feed(index)
    links = []
    for href in parser.links:
        url = urljoin(root, href)
        parts = urlsplit(url)
        if (parts.scheme == 'https' and parts.netloc == urlsplit(root).netloc
                and parts.path.startswith('/news/') and parts.path != '/news/'
                and not parts.query and not parts.fragment and url not in links):
            links.append(url)
    rows, seen = [], set()
    for url in links[:4]:
        try:
            html = fetch(url, limit=2 * 1024 * 1024).decode('utf-8', errors='replace')
        except (ImageSourceError, OSError):
            continue
        for asset in album_assets(html):
            if not isinstance(asset, dict) or asset.get('assetType') != 'image':
                continue
            file = asset.get('file')
            if not isinstance(file, dict):
                continue
            original = file.get('url')
            if not isinstance(original, str):
                continue
            parts = urlsplit(original)
            if (parts.scheme != 'https' or parts.netloc != profile['asset_host']
                    or not parts.path.startswith('/uploads/assets/') or parts.query or parts.fragment
                    or file.get('mime') not in {'image/jpeg', 'image/png', 'image/webp'}):
                continue
            w, h = file.get('width'), file.get('height')
            if type(w) is not int or type(h) is not int or min(w, h) < 600 or max(w, h) < 1000:
                continue
            if original in seen:
                continue
            title = asset.get('title') or file.get('alternativeText') or file.get('name')
            if not isinstance(title, str) or not title.strip():
                continue
            seen.add(original)
            rows.append({'provider': 'official_media',
                'asset_id': 'official:' + hashlib.sha256(original.encode()).hexdigest()[:20],
                'title': title[:250], 'description': subject + ': ' + title[:250],
                'download_url': original, 'original_url': original, 'source_url': url,
                'width': w, 'height': h, 'credit': profile['credit'],
                'license': 'All rights reserved', 'terms_url': profile['terms'],
                'rights_status': 'permission_required', 'licensing_verified': False,
                'image_role': 'official media asset; verify relevance and usage before publication'})
            if len(rows) >= limit:
                return rows
    return rows


# Owner's explicit editorial-use decision, 2026-09-22:
# «لاتشيل هم التصريح. خذ الصور وانا المسؤول»
# Records the owner's decision, not a license grant from the copyright holder.
OWNER_USE_DECISION = 'owner-official-editorial-use-2026-09-22'


def official_source_asset(row):
    if not isinstance(row, dict) or row.get('provider') != 'official_media':
        return False
    try:
        source = urlsplit(row['source_url'])
        original = row['original_url']
        asset = urlsplit(original)
        profile = next((p for p in PROFILES if urlsplit(p['newsroom']).netloc == source.netloc), None)
        return bool(profile and source.scheme == asset.scheme == 'https'
            and source.path.startswith('/news/') and source.path != '/news/'
            and not source.query and not source.fragment
            and asset.netloc == profile['asset_host']
            and re.fullmatch(r'/uploads/assets/[^/]+\.(?:jpg|jpeg|png|webp)', asset.path, re.I)
            and not asset.query and not asset.fragment
            and row.get('download_url') == original
            and row.get('asset_id') == 'official:' + hashlib.sha256(original.encode()).hexdigest()[:20]
            and row.get('terms_url') == profile['terms']
            and row.get('license') == 'All rights reserved')
    except (KeyError, TypeError, ValueError):
        return False


def owner_editorial_use(row):
    return (official_source_asset(row)
            and row.get('owner_use_decision') == OWNER_USE_DECISION
            and row.get('rights_status') == 'owner_accepted_editorial_use')


def varied_official_images(rows):
    """Offer distinct visual roles before filling the bounded download pool."""
    selected = []
    for pattern in (r'exterior|front view', r'cockpit|interior|seats', r'doors',
                    r'factory|manufactur', r'logo', r'charging|charger'):
        item = next((i for i, row in enumerate(rows) if i not in selected
                     and re.search(pattern, row.get('title', ''), re.I)), None)
        if item is not None:
            selected.append(item)
    selected.extend(i for i in range(len(rows)) if i not in selected)
    return [rows[i] for i in selected]
