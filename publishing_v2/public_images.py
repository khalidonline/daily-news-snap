"""Public image acquisition for isolated review; never authorizes publication."""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import warnings
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image

HOSTS = {'apod.nasa.gov', 'commons.wikimedia.org', 'upload.wikimedia.org', 'thumb.wikimedia.org', 'images-api.nasa.gov', 'images-assets.nasa.gov'}
MAX_BYTES = 16 * 1024 * 1024
MAX_PIXELS = 40_000_000
NASA_TERMS = 'https://www.nasa.gov/nasa-brand-center/images-and-media/'


class ImageSourceError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ImageSourceError('redirect_rejected')


def validate_url(url):
    try:
        parts = urlsplit(url)
        valid = (parts.scheme == 'https' and parts.hostname in HOSTS and not parts.username
                 and not parts.password and parts.port in (None, 443) and not parts.fragment)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ImageSourceError('url_rejected')


def get_bytes(url, *, limit=MAX_BYTES):
    validate_url(url)
    request = Request(url, headers={'User-Agent': 'DailyNewsSnap/2.0 (https://github.com/khalidonline/daily-news-snap)'})
    try:
        with build_opener(NoRedirect()).open(request, timeout=12) as response:
            data = response.read(limit + 1)
    except HTTPError as error:
        raise ImageSourceError(f'http_{error.code}') from None
    except Exception:
        raise ImageSourceError('request_failed') from None
    if len(data) > limit:
        raise ImageSourceError('too_large')
    return data


def get_json(url):
    try:
        return json.loads(get_bytes(url, limit=2 * 1024 * 1024))
    except (ValueError, UnicodeError):
        raise ImageSourceError('malformed_json') from None


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    parser = PlainText()
    parser.feed(value if isinstance(value, str) else '')
    return ' '.join(' '.join(parser.parts).split())[:12000]


def query_params(query, limit):
    if not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise ValueError('query must contain 1-200 characters')
    if type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError('limit must be 1-5')


def search_commons(query, limit=5):
    query_params(query, limit)
    params = {'action': 'query', 'format': 'json', 'formatversion': 2, 'generator': 'search',
              'gsrsearch': query, 'gsrnamespace': 6, 'gsrlimit': limit, 'prop': 'imageinfo',
              'iiprop': 'url|mime|extmetadata', 'iiurlwidth': 1600}
    response = get_json('https://commons.wikimedia.org/w/api.php?' + urlencode(params))
    if not isinstance(response, dict) or 'error' in response:
        raise ImageSourceError('malformed_response')
    pages = response.get('query', {}).get('pages', [])
    results = []
    for page in pages[:limit]:
        try:
            info = page['imageinfo'][0]
            if info.get('mime') not in {'image/jpeg', 'image/png', 'image/webp'}:
                continue
            meta = info.get('extmetadata', {})
            field = lambda name: plain(meta.get(name, {}).get('value', ''))
            url = info.get('thumburl') or info['url']
            validate_url(url)
            results.append({'provider': 'commons', 'asset_id': str(page['pageid']), 'title': plain(page['title']),
                'description': field('ImageDescription'), 'download_url': url, 'original_url': info['url'],
                'source_url': info['descriptionurl'], 'credit': field('Artist'), 'credit_line': field('Credit'),
                'license': field('LicenseShortName'), 'license_url': field('LicenseUrl'),
                'attribution_required': field('AttributionRequired'), 'restrictions': field('Restrictions'),
                'date_created': field('DateTimeOriginal'), 'licensing_verified': False})
        except (KeyError, IndexError, TypeError, ImageSourceError):
            continue
    return results


def search_nasa(query, limit=5):
    query_params(query, limit)
    response = get_json('https://images-api.nasa.gov/search?' + urlencode({'q': query, 'media_type': 'image', 'page_size': limit}))
    try:
        items = response['collection']['items']
        if not isinstance(items, list): raise TypeError()
    except (KeyError, TypeError):
        raise ImageSourceError('malformed_response') from None
    results = []
    for item in items[:limit]:
        try:
            data = item['data'][0]
            if data.get('media_type') != 'image': continue
            asset_id = data['nasa_id']
            assets = get_json('https://images-api.nasa.gov/asset/' + quote(asset_id, safe=''))['collection']['items']
            urls = [a['href'] for a in assets if isinstance(a, dict) and isinstance(a.get('href'), str)
                    and urlsplit(a['href']).path.lower().endswith(('.jpg', '.jpeg', '.png'))]
            # Prefer a large rendition; the byte/dimension checks still decide usability.
            urls.sort(key=lambda u: (0 if '~large.' in u else 1 if '~orig.' in u else 2))
            for url in urls:
                parts = urlsplit(url)
                if parts.scheme == 'http' and parts.netloc == 'images-assets.nasa.gov':
                    url = urlunsplit(('https', parts.netloc, parts.path, parts.query, parts.fragment))
                try: validate_url(url)
                except ImageSourceError: continue
                results.append({'provider': 'nasa', 'asset_id': asset_id, 'title': plain(data.get('title', '')),
                    'description': plain(data.get('description', '')), 'source_url': 'https://images.nasa.gov/details/' + quote(asset_id, safe=''),
                    'download_url': url, 'credit': plain(data.get('photographer') or data.get('secondary_creator') or data.get('center', 'NASA')),
                    'license': 'review_required', 'license_url': NASA_TERMS, 'date_created': data.get('date_created'),
                    'licensing_verified': False})
                break
        except ImageSourceError as error:
            if str(error) == 'http_429':
                if results: return results
                raise
            continue
        except (KeyError, IndexError, TypeError):
            continue
    return results


def inspect_image(data):
    if not isinstance(data, bytes) or not data or len(data) > MAX_BYTES:
        raise ImageSourceError('invalid_size')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
                fmt = image.format
                if fmt not in {'JPEG', 'PNG', 'WEBP'} or width * height > MAX_PIXELS:
                    raise ImageSourceError('invalid_image')
                if min(width, height) < 600 or max(width, height) < 1000:
                    raise ImageSourceError('insufficient_resolution')
                if getattr(image, 'n_frames', 1) != 1:
                    raise ImageSourceError('animated_image')
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
    except ImageSourceError:
        raise
    except Exception:
        raise ImageSourceError('invalid_image') from None
    return width, height, {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}[fmt]


def atomic_write(path, data):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def store_candidate(candidate, output, *, fetch=None):
    """Store original fetched bytes and review provenance, not a publication approval."""
    validate_url(candidate['download_url'])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data = (fetch or get_bytes)(candidate['download_url'])
    width, height, suffix = inspect_image(data)
    digest = hashlib.sha256(data).hexdigest()
    filename = digest + suffix
    path = output / filename
    if path.exists() and (path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
        raise ImageSourceError('stored_asset_corrupt')
    if not path.exists(): atomic_write(path, data)
    receipt = {**candidate, 'file': filename, 'sha256': digest, 'width': width, 'height': height,
               'bytes': len(data), 'visual_approved': False, 'licensing_verified': False,
               'relevance_verified': False, 'production_ready': False}
    receipt_bytes = json.dumps(receipt, ensure_ascii=False, sort_keys=True).encode()
    manifest = hashlib.sha256(receipt_bytes).hexdigest() + '.json'
    atomic_write(output / manifest, receipt_bytes)
    return {**receipt, 'manifest': manifest}


def acquire(query, output, *, sources=None, fetch=None, frame_brief=None, reviewer=None):
    query_params(query, 5)
    screening = reviewer is not None
    if screening and (not callable(reviewer) or not isinstance(frame_brief, dict) or not frame_brief):
        raise ValueError('screening_requires_frame_brief_and_reviewer')
    if frame_brief is not None and not screening:
        raise ValueError('frame_brief_requires_reviewer')
    # Snapshot the caller's complete context before any external callback can mutate it.
    brief_json = json.dumps(frame_brief, ensure_ascii=False, sort_keys=True, allow_nan=False)
    sources = sources if sources is not None else [('commons', search_commons), ('nasa', search_nasa)]
    attempts = []
    for provider, search in sources:
        try:
            candidates = search(query)
            if not isinstance(candidates, list): raise ImageSourceError('malformed_response')
        except Exception:
            attempts.append({'provider': provider, 'status': 'source_failed'})
            continue
        if not candidates: attempts.append({'provider': provider, 'status': 'no_candidates'})
        for candidate in candidates[:5]:
            try:
                if candidate['provider'] != provider: raise ImageSourceError('provider_mismatch')
                result = store_candidate(candidate, output, fetch=fetch)
            except ImageSourceError as error:
                if str(error) == 'http_429':
                    attempts.append({'provider': provider, 'status': 'rate_limited'})
                    break
                attempts.append({'provider': provider, 'status': 'candidate_failed'})
                continue
            except Exception:
                attempts.append({'provider': provider, 'status': 'candidate_failed'})
                continue
            if screening:
                try:
                    decision = reviewer(dict(result), Path(output) / result['file'], json.loads(brief_json))
                    checks = ('relevant', 'crop_suitable', 'historically_appropriate')
                    if not isinstance(decision, dict) or any(type(decision.get(k)) is not bool for k in checks):
                        raise ValueError('invalid_review')
                    reason = decision.get('reason')
                    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
                        raise ValueError('invalid_review_reason')
                    # A review records evidence; it never grants publication or licensing approval.
                    review = {'asset_sha256': result['sha256'], 'asset_manifest': result['manifest'],
                              'frame_brief': json.loads(brief_json),
                              'decision': {k: decision[k] for k in checks}, 'reason': reason,
                              'production_ready': False}
                    if hashlib.sha256((Path(output) / result['file']).read_bytes()).hexdigest() != result['sha256']:
                        raise ValueError('asset_changed_during_review')
                    encoded = json.dumps(review, ensure_ascii=False, sort_keys=True).encode()
                    review_manifest = 'review-' + hashlib.sha256(encoded).hexdigest() + '.json'
                    atomic_write(Path(output) / review_manifest, encoded)
                    if not all(decision[k] is True for k in checks):
                        attempts.append({'provider': provider, 'status': 'review_rejected', 'review_manifest': review_manifest})
                        continue
                except Exception:
                    attempts.append({'provider': provider, 'status': 'review_failed'})
                    continue
                return {'status': 'screened_review_required', 'asset': result, 'review_manifest': review_manifest,
                        'attempts': attempts, 'production_ready': False}
            return {'status': 'downloaded_review_required', 'asset': result, 'attempts': attempts, 'production_ready': False}
    return {'status': 'no_suitable_image' if screening else 'no_download', 'attempts': attempts, 'production_ready': False}
