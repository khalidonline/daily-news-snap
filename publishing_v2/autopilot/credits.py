"""Complete, bounded CC BY 2.0 and 4.0 attribution in a reviewed final image frame.

License conditions: https://creativecommons.org/licenses/by/4.0/legalcode.en#s3
The Commons material URI also exposes supplied notices and modification history.
"""
import re
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageDraw, ImageFont, ImageOps

LICENSE_URL = 'https://creativecommons.org/licenses/by/4.0/'
LICENSE_URLS = {f'CC BY {version}': f'https://creativecommons.org/licenses/by/{version}/'
                for version in ('2.0', '3.0', '4.0')}  # 3.0: owner approved 2026-09-26 (same attribution terms)
NOTICE_FIELDS = ('copyright_notice', 'attribution_notice', 'usage_terms', 'disclaimer', 'rights_links')
FONT_ROOT = Path(__file__).resolve().parents[2] / 'fonts'


def attribution_eligible(row):
    if not isinstance(row, dict):
        return False
    if row.get('license') not in LICENSE_URLS or row.get('restrictions'):
        return False
    license_url = LICENSE_URLS[row['license']]
    if row.get('license_url') not in {license_url, license_url.rstrip('/'), license_url.replace('https:', 'http:'),
                                       license_url.replace('https:', 'http:').rstrip('/')}:
        return False
    for key, maximum in (('credit', 120), ('title', 180), ('credit_line', 200)) + tuple((key, 400) for key in NOTICE_FIELDS):
        value = row.get(key, '')
        if not isinstance(value, str) or len(value) > maximum:
            return False
        if key in {'credit', 'title'} and not value.strip():
            return False
        if any(ord(char) < 32 and char not in '\n\t\r' for char in value):
            return False
    # Commons templates can repeat a placeholder, even without whitespace
    # after HTML stripping. Normalize separators only for this validation;
    # retain the original supplied credit for rendering.
    credit_key = ''.join(char for char in row['credit'].casefold() if char.isalnum())
    if (credit_key in {'na', 'none'}
            or re.fullmatch(r'(?:unknown(?:author|artist|photographer|creator)?|authorunknown|ownwork|self)+',
                            credit_key)):
        return False
    try:
        url = urlsplit(row.get('source_url', ''))
        flickr = row.get('provider') == 'flickr'
        identity = str(row.get('asset_id', ''))
        if flickr:
            match = re.fullmatch(r'flickr:([0-9]+)', identity)
            if (not match or row.get('source_verified') is not True or url.query
                    or not re.fullmatch(r'/photos/[^/]+/' + match[1] + r'/?', url.path)):
                return False
        elif row.get('provider', 'commons') != 'commons' or not identity.isdigit():
            return False
        if (url.scheme != 'https' or url.hostname != ('www.flickr.com' if flickr else 'commons.wikimedia.org')
                or url.username or url.password or url.port not in (None, 443) or url.fragment):
            return False
    except (TypeError, ValueError):
        return False
    return True


def _font(size, bold=False):
    return ImageFont.truetype(str(FONT_ROOT / ('Almarai-Bold.ttf' if bold else 'Almarai-Regular.ttf')), size)


def _direction(text):
    return 'rtl' if re.search(r'[\u0600-\u06ff]', text) else 'ltr'


def _blocks(package):
    assets = {}
    for card in package.get('cards', []):
        image = card.get('image', {})
        if image.get('license') in LICENSE_URLS:
            if not attribution_eligible(image):
                raise ValueError('incomplete_image_attribution')
            identity = str(image['asset_id'])
            if identity in assets and any(assets[identity].get(key) != image.get(key)
                    for key in ('title', 'credit', 'credit_line', 'license', 'license_url') + NOTICE_FIELDS):
                raise ValueError('conflicting_image_attribution')
            assets[identity] = image
    if len(assets) > 6:
        raise ValueError('too_many_credited_assets')
    blocks = [('المصادر وحقوق الصور', True)]
    if assets:
        blocks.append(('Photo credits', True))
        for number, (identity, row) in enumerate(assets.items(), 1):
            blocks.append((f"{number}. {row['title']}", True))
            blocks.append((row['credit'], False))
            if row.get('credit_line') and row['credit_line'].strip() != row['credit'].strip():
                blocks.append((row['credit_line'], False))
            for key in NOTICE_FIELDS:
                if row.get(key):
                    blocks.append((row[key], False))
            blocks.append((row['source_url'] if row.get('provider') == 'flickr'
                           else f'https://commons.wikimedia.org/?curid={identity}', False))
            blocks.append((row['license'], False))
            blocks.append((LICENSE_URLS[row['license']], False))
        blocks.append(('Images cropped/resized. No endorsement implied.', False))
    from publishing_v2.official_images import owner_editorial_use
    from publishing_v2.primary_images import owner_primary_use
    official = {c.get('image', {}).get('source_url'): c.get('image', {})
                for c in package.get('cards', [])
                if owner_editorial_use(c.get('image')) or owner_primary_use(c.get('image', {}))}
    if official:
        blocks.append(('Source media · owner-directed editorial use', False))
        for url, row in official.items():
            blocks.append((row.get('credit', '') + ' · ' + url, False))
    elif not assets:
        blocks.append(('Images: public domain / CC0', False))
    names = {'bbc.com':'BBC', 'bbc.co.uk':'BBC', 'alyaum.com':'اليوم',
             'aawsat.com':'الشرق الأوسط', 'en.wikipedia.org':'Wikipedia', 'ar.wikipedia.org':'ويكيبيديا'}
    hosts = []
    for source in package.get('sources', []):
        try:
            host = urlsplit(source.get('url', '')).hostname
        except ValueError:
            raise ValueError('invalid_editorial_source') from None
        if not host:
            raise ValueError('invalid_editorial_source')
        host = host.removeprefix('www.')
        if host not in hosts:
            hosts.append(host)
    if hosts:
        blocks.append(('المصادر التحريرية', True))
        blocks.extend((f'{names[host]} · {host}' if host in names else host, False) for host in hosts)
    return blocks


def _wrap(draw, text, font, width):
    # Preserve every character (including long URLs); only insert line breaks.
    lines = []
    for paragraph in text.splitlines() or ['']:
        line = ''
        for token in re.findall(r'\S+\s*', paragraph):
            if draw.textlength(line + token, font=font, direction=_direction(line + token)) <= width:
                line += token
                continue
            if line:
                lines.append(line.rstrip()); line = ''
            for char in token:
                if line and draw.textlength(line + char, font=font, direction=_direction(line + char)) > width:
                    lines.append(line.rstrip()); line = ''
                line += char
        lines.append(line.rstrip())
    return lines


def _layout(package):
    blocks = _blocks(package)
    draw = ImageDraw.Draw(Image.new('RGB', (1080, 1920)))
    for size in (34, 32, 30, 28, 26):
        rows, y = [], 390
        for text, bold in blocks:
            font = _font(size, bold)
            for line in _wrap(draw, text, font, 952):
                direction = _direction(line)
                box = draw.textbbox((0, 0), line, font=font, direction=direction)
                width, height = box[2] - box[0], box[3] - box[1]
                x = 1016-width if direction == 'rtl' else 64
                rows.append({'text':line, 'size':size, 'bold':bold, 'direction':direction,
                             'bounds':(x, y, x+width, y+height), 'origin':(x-box[0], y-box[1])})
                y += max(height+8, size+8)
            y += 6
        if y <= 1820 and all(row['bounds'][2] <= 1016 for row in rows):
            return rows
    raise ValueError('credits_layout_overflow')


def render_credits(package, source_path, target):
    """Render complete attribution or raise before writing an incomplete frame."""
    rows = _layout(package)
    canvas = Image.new('RGB', (1080, 1920), '#f7f4ee')
    draw = ImageDraw.Draw(canvas)
    with Image.open(source_path) as source:
        strip = ImageOps.fit(source.convert('RGB'), (952, 248), Image.Resampling.LANCZOS)
        canvas.paste(strip, (64, 104))
    brand = 'ملخص تنفيذي'
    font = _font(28, True)
    draw.text((1016, 54), brand, font=font, fill='#17483f', direction='rtl', anchor='ra')
    draw.line((64, 372, 1016, 372), fill='#c9bb9c', width=3)
    for row in rows:
        draw.text(row['origin'], row['text'], font=_font(row['size'], row['bold']),
                  fill='#183b35' if row['bold'] else '#26352f', direction=row['direction'])
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, 'JPEG', quality=95, subsampling=0)
    return target


def public_attribution_layout(image):
    """Two-word maximum display label; complete notices stay in package metadata."""
    if not attribution_eligible(image):
        raise ValueError('incomplete_image_attribution')
    label = image['credit'].strip()
    if len(label.split()) > 2:
        # Name the actual source provider instead of truncating a person's name.
        label = 'Flickr' if image.get('provider') == 'flickr' else 'Wikimedia Commons'
    draw = ImageDraw.Draw(Image.new('RGB', (1080, 1920)))
    if draw.textlength(label, font=_font(24)) > 952:
        raise ValueError('public_attribution_layout_overflow')
    return [label], 48


def public_attribution_eligible(image):
    try:
        public_attribution_layout(image)
        return True
    except (ValueError, TypeError, KeyError):
        return False


def attribution_identity(image):
    import hashlib
    import json
    return hashlib.sha256(json.dumps(image, sort_keys=True, ensure_ascii=False,
                                      separators=(',', ':')).encode()).hexdigest()


def render_public_attribution(card, path):
    """Owner-directed compact source label without shrinking the approved design."""
    import hashlib
    rows, _ = public_attribution_layout(card['image'])
    with Image.open(path) as original:
        if original.size != (1080, 1920):
            raise ValueError('wrong_frame_dimensions')
        canvas = original.convert('RGB')
    draw = ImageDraw.Draw(canvas)
    draw.text((540, 1850), rows[0], font=_font(24), fill='#79736b', anchor='mt')
    canvas.save(path, 'JPEG', quality=95, subsampling=0)
    card['public_attribution'] = {
        'version': 3, 'display_label': rows[0],
        'image_sha256': attribution_identity(card['image']),
        'media_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def render_compact_attribution(package, paths, source_path):
    """Short labels with a hash-bound internal credits record.

    Input paths must be clean editorial renders without the older rights band.
    Preserve complete attribution metadata; never publish the companion.
    """
    import hashlib
    cards = package['cards']
    if len(paths) != len(cards) or cards[-1].get('kind') != 'credits':
        raise ValueError('compact_attribution_companion_required')
    selected = []
    for card, path in zip(cards[:-1], paths[:-1]):
        if card.get('image', {}).get('license') not in LICENSE_URLS:
            continue
        if not attribution_eligible(card['image']):
            raise ValueError('incomplete_image_attribution')
        label = card['image']['credit'].strip()
        if not 1 <= len(label.split()) <= 2:
            raise ValueError('compact_credit_needs_owner_label')
        with Image.open(path) as original:
            canvas = original.convert('RGB')
        if canvas.size != (1080, 1920):
            raise ValueError('wrong_frame_dimensions')
        draw = ImageDraw.Draw(canvas)
        draw.text((540, 1850), label, font=_font(24), fill='#79736b', anchor='mt')
        canvas.save(path, 'JPEG', quality=95, subsampling=0)
        selected.append((card, path))
    render_credits(package, source_path, paths[-1])
    digest = hashlib.sha256(Path(paths[-1]).read_bytes()).hexdigest()
    cards[-1]['sha256'] = digest
    cards[-1]['attribution_companion'] = {
        'media_sha256': digest,
        'images': [attribution_identity(card['image']) for card, _ in selected]}
    for card, path in selected:
        card['public_attribution'] = {
            'version': 2, 'image_sha256': attribution_identity(card['image']),
            'media_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'companion_sha256': digest}
