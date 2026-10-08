"""Offline compact-card preflight. Measurements complement, never replace, visual review.

The renderer must record the actual text, sizes and boxes used in the final JPG.
Reports bind the ordered image bytes; an edit invalidates the previous report.
"""
import hashlib
import io
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT_ROOT = Path(__file__).resolve().parents[1] / 'fonts'
CTA = 'شاركها مع صديقك اللي تعجبه هذي المعلومة'

class ReadabilityError(ValueError):
    pass

def fail(message):
    raise ReadabilityError('Readability: ' + message)

def measure(block, *, minimum, maximum_lines, bold):
    if not isinstance(block, dict): fail('missing text measurements')
    text, size, box = block.get('text'), block.get('size'), block.get('box')
    if not isinstance(text, str) or not text.strip(): fail('empty text')
    if (type(size) not in (int, float) or not math.isfinite(size)
            or size < minimum or size > 120): fail('font too small or invalid')
    if (not isinstance(box, list) or len(box) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)):
        fail('invalid text box')
    x0, y0, x1, y1 = box
    if not (60 <= x0 < x1 <= 1020 and 260 <= y0 < y1 <= 1810):
        fail('text outside content safe area')
    font = ImageFont.truetype(str(FONT_ROOT / ('Almarai-Bold.ttf' if bold else 'Almarai-Regular.ttf')), int(size))
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    width = x1 - x0
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split():
            if draw.textlength(word, font=font, direction='rtl') > width: fail('unbreakable text overflow')
            trial = (line + ' ' + word).strip()
            if draw.textlength(trial, font=font, direction='rtl') > width:
                lines.append(line); line = word
            else:
                line = trial
        lines.append(line)
    if len(lines) > maximum_lines: fail('too many text lines; shorten copy, do not shrink font')
    if len(lines) * math.ceil(size * 1.3) > y1 - y0: fail('text box too short')
    return box

def validate_readability(report_path, media):
    if not 1 <= len(media) <= 2: fail('compact packages require one or two cards')
    try:
        report = json.loads(Path(report_path).read_text())
    except (OSError, ValueError):
        fail('missing or invalid readability report')
    if not isinstance(report, dict) or report.get('version') != 1: fail('unsupported report')
    review = report.get('visual_review', {})
    if (not isinstance(review, dict) or review.get('approved') is not True
            or not isinstance(review.get('reference'), str) or not review['reference'].strip()):
        fail('mobile visual review required')
    cards = report.get('cards')
    if not isinstance(cards, list) or len(cards) != len(media): fail('card count mismatch')
    for card, (_, content) in zip(cards, media):
        if not isinstance(card, dict) or card.get('sha256') != hashlib.sha256(content).hexdigest():
            fail('image changed after readability review')
        with Image.open(io.BytesIO(content)) as image:
            if image.size != (1080, 1920): fail('measurements require 1080x1920 images')
            image.verify()
        bullets = card.get('bullets')
        if not isinstance(bullets, list) or not 1 <= len(bullets) <= 3: fail('expected one to three bullets')
        boxes = [measure(card.get('headline'), minimum=48, maximum_lines=1, bold=True)]
        boxes += [measure(b, minimum=48, maximum_lines=2, bold=False) for b in bullets]
        layout = card.get('layout', 'information')
        if layout == 'visual_challenge':
            if 'cta' in card: fail('challenge must not duplicate its closing with an information CTA')
            boxes.append(measure(card.get('closing'), minimum=38, maximum_lines=2, bold=True))
        elif layout == 'information':
            if not isinstance(card.get('cta'), dict) or card['cta'].get('text') not in (CTA, 'شاركها مع صديقك اللي تعجبه المعلومة'): fail('use approved sharing text')
            boxes.append(measure(card.get('cta'), minimum=38, maximum_lines=2, bold=True))
        else:
            fail('unsupported card layout')
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3]):
                    fail('overlapping text boxes')
    return {'status': 'readability_validated', 'card_count': len(cards), 'preview_width': 390}

def require_for_new_delivery(manifest, media, existing):
    """Do not interrupt reconciliation or recreate any existing delivery attempt."""
    if existing.get('_group') or all(
            isinstance(existing.get(str(i)), dict) and existing[str(i)].get('post_id')
            for i in range(1, len(media) + 1)):
        return
    path = Path(manifest).resolve()
    validate_readability(path.parent / 'readability.json', media)
