"""Bounded public Flickr discovery; each result is rechecked on its photo page.

No API key, paid requests, local photo collection, or executed page scripts.
If public structured metadata changes, reject the result and let recovery continue.
"""
import json
import re
import time
from urllib.parse import urlencode, urlsplit, quote
from .public_images import get_bytes, plain, validate_url, ImageSourceError, query_params


def _models(html):
    match = re.search(r'\bmodelExport:\s*', html)
    if not match:
        raise ImageSourceError('flickr_metadata_missing')
    try:
        return json.JSONDecoder().raw_decode(html[match.end():])[0]['main']
    except (ValueError, KeyError, TypeError):
        raise ImageSourceError('flickr_metadata_changed') from None


def _page_id(url):
    validate_url(url)
    part = urlsplit(url)
    match = re.fullmatch(r'/photos/[^/]+/([0-9]+)/?', part.path)
    if part.hostname != 'www.flickr.com' or part.query or not match:
        raise ImageSourceError('flickr_photo_url_rejected')
    return match[1]


def photo(url):
    identity = _page_id(url)
    html = get_bytes(url, limit=2_000_000).decode('utf-8')
    rows = _models(html).get('photo-models', [])
    models = [r['data'] for r in rows if isinstance(r.get('data'), dict)
              and str(r['data'].get('id')) == identity]
    if len(models) != 1:
        raise ImageSourceError('flickr_photo_identity_mismatch')
    model = models[0]
    # Require independent agreement between the page's model and ImageObject.
    if model.get('license') != 4 or model.get('safetyLevel') != 0:
        raise ImageSourceError('flickr_rights_not_supported')
    objects = []
    for match in re.finditer(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(match[1])
            objects.extend(data.get('@graph', [data]))
        except (ValueError, AttributeError):
            continue
    records = [r for r in objects if r.get('@type') == 'ImageObject'
               and r.get('license') == 'https://creativecommons.org/licenses/by/2.0/']
    records = [r for r in records if _page_id(r.get('acquireLicensePage', '')) == identity]
    if len(records) != 1:
        raise ImageSourceError('flickr_license_unverified')
    record = records[0]
    renditions = []
    for item in model.get('sizes', {}).get('data', {}).values():
        size = item.get('data', {})
        candidate = size.get('url', '')
        if candidate.startswith('//'): candidate = 'https:' + candidate
        validate_url(candidate)
        part = urlsplit(candidate)
        if (part.hostname != 'live.staticflickr.com' or
                not re.fullmatch(r'/[0-9]+/' + identity + r'_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)?\.(?:jpg|png)', part.path)):
            continue
        width, height = size.get('width'), size.get('height')
        if type(width) is int and type(height) is int and min(width, height) >= 600 and max(width, height) >= 1000:
            renditions.append((width * height, candidate, width, height))
    if not renditions:
        raise ImageSourceError('flickr_insufficient_resolution')
    renditions.sort()
    _, download, width, height = renditions[0]
    author = record.get('author', {})
    return {'provider':'flickr', 'asset_id':'flickr:' + identity,
            'title':plain(model.get('title')), 'description':plain(model.get('description')),
            'source_url':record['acquireLicensePage'].rstrip('/') + '/',
            'download_url':download, 'original_url':renditions[-1][1],
            'width':width, 'height':height, 'credit':plain(author.get('name')),
            'credit_line':plain(record.get('creditText', '')), 'copyright_notice':plain(record.get('copyrightNotice', '')),
            'rights_links':author.get('url', ''), 'license':'CC BY 2.0',
            'license_url':record['license'], 'restrictions':'', 'attribution_required':'true',
            'source_verified':True, 'licensing_verified':False,
            'date_created':plain(record.get('dateCreated', '')), 'image_role':'subject illustration; event date unverified'}


def search_flickr(query, limit=5, *, deadline=None, accept_metadata=None):
    query_params(query, limit)
    html = get_bytes('https://www.flickr.com/search/?' + urlencode(
        {'text':query, 'license':'4', 'sort':'relevance'}), limit=2_000_000).decode('utf-8')
    search = _models(html).get('search-photos-lite-models', [])
    if not search:
        raise ImageSourceError('flickr_search_metadata_missing')
    rows = search[0]['data']['photos']['data']['_data']
    results, seen = [], set()
    checked = 0
    for row in rows[:25]:
        if checked >= limit: break
        if deadline is not None and time.monotonic() >= deadline: break
        data = row.get('data', {})
        if not isinstance(data, dict): continue
        if accept_metadata and not accept_metadata({'title':plain(data.get('title')), 'description':plain(data.get('description'))}):
            continue
        identity = str(data.get('id', ''))
        owner = data.get('pathAlias') or data.get('ownerNsid')
        if not identity.isdigit() or not isinstance(owner, str) or not owner or identity in seen:
            continue
        seen.add(identity)
        checked += 1
        try:
            results.append(photo('https://www.flickr.com/photos/' + quote(owner, safe='') + '/' + identity + '/'))
        except (ImageSourceError, ValueError, KeyError, TypeError):
            continue
    return results
