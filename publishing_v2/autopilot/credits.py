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
                for version in ('2.0', '4.0')}
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
    else:
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
