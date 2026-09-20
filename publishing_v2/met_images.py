"""Bounded Met Open Access discovery for historical objects, not current people.

Rights: https://www.metmuseum.org/policies/image-resources
API: https://metmuseum.github.io/ (v1.1 paginated search).
"""
import re
import time
from urllib.parse import urlencode, urlsplit
from .public_images import get_json, plain, ImageSourceError

API = 'https://collectionapi.metmuseum.org/public/collection/'
# Conservative routing only. Source metadata must still match the actual subject
# in Sources; this list never rewrites identity or supplies fabricated aliases.
OBJECTS = re.compile(r'\b(coffee|teapot|cloak|abaya|bisht|textile|carpet|ceramic|pottery|'
                     r'jewel(?:ry|lery)|sword|armor|armour|helmet|perfume|incense|'
                     r'porcelain|watch|clock)\b', re.I)


def search_met(query, limit=3, *, deadline=None):
    if not isinstance(query, str) or not query.strip() or len(query) > 130:
        return []
    if type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError('limit must be 1-5')
    if not OBJECTS.search(query):
        return []
    end = min(deadline if deadline is not None else float('inf'), time.monotonic() + 45)
    if time.monotonic() >= end:
        return []
    data = get_json(API + 'v1.1/search?' + urlencode(dict(q=query, hasImages='true', limit=limit, offset=0)))
    ids = data.get('objectIDs') if isinstance(data, dict) else None
    if ids is None:
        return []
    if not isinstance(ids, list):
        raise ImageSourceError('malformed_met_search')
    unique = list(dict.fromkeys(i for i in ids if type(i) is int and i > 0))[:limit]
    results = []
    for ident in unique:
        if time.monotonic() >= end:
            break
        try:
            row = get_json(API + f'v1/objects/{ident}')
            if not isinstance(row, dict) or type(row.get('objectID')) is not int or row['objectID'] != ident:
                continue
            if row.get('isPublicDomain') is not True:
                continue
            url = row.get('primaryImage')
            if not isinstance(url, str) or not url:
                continue
            parts = urlsplit(url)
            if (parts.scheme != 'https' or parts.hostname != 'images.metmuseum.org'
                    or parts.username or parts.password or parts.port not in (None,443)
                    or parts.query or parts.fragment or not parts.path.startswith('/CRDImages/')
                    or not parts.path.lower().endswith(('.jpg','.jpeg'))):
                continue
            title = plain(row.get('title'))
            if not title:
                continue
            description = '; '.join(f'{key}: {plain(row.get(key))}' for key in
                ('title','objectName','culture','country','region','city','objectDate','medium') if row.get(key))
            results.append(dict(provider='met', asset_id=f'met:{ident}', title=title,
                description=description, country=plain(row.get('country')), date_created=plain(row.get('objectDate')),
                source_url=f'https://www.metmuseum.org/art/collection/search/{ident}',
                download_url=url, original_url=url, license='CC0',
                license_url='https://creativecommons.org/publicdomain/zero/1.0/',
                credit='The Metropolitan Museum of Art', credit_line=plain(row.get('creditLine')),
                attribution_required='false', restrictions='', source_verified=True,
                licensing_verified=True, image_role='historical object; preserve origin and date; not current-event evidence'))
        except (ImageSourceError, ValueError, TypeError):
            continue
    return results
