"""Pre-review information copy gate. No publication or automatic truncation."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import unicodedata

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def wrap_text(text, font, draw, left, right):
    """Exact wrapping shared with the fixed renderer (not a character heuristic)."""
    lines = []
    line = ''
    for word in text.split():
        trial = (line + ' ' + word).strip()
        measured = draw.textbbox((0, 0), trial, font=font, direction='rtl')
        if measured[2] - measured[0] > right-left-2:
            if not line:
                raise ValueError('overflow: unbreakable word')
            lines.append(line)
            line = word
            if draw.textlength(word, font=font, direction='rtl') > right-left:
                raise ValueError('overflow: unbreakable word')
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _receipt(draft):
    return {
        'text_sha256': _hash(json.dumps(draft, ensure_ascii=False, sort_keys=True).encode()),
        'settings_sha256': _hash((ROOT/'publishing_v2/design-settings.json').read_bytes()),
        'fonts': {w: _hash((ROOT/f'fonts/Almarai-{w}.ttf').read_bytes())
                  for w in ('Regular', 'Bold')},
        'implementation': {name: _hash((ROOT/'publishing_v2'/name).read_bytes()) for name in
                           ('information_text_fit.py', 'fixed_information_template.py', 'design_contract.py')},
    }


def measure_card(draft):
    result = dict(fit=False, fields=[], violations=[])
    if not isinstance(draft, dict):
        result['violations'].append('Expected an object')
        return result
    bullets = draft.get('bullets')
    if not isinstance(bullets, list) or not 1 <= len(bullets) <= 4:
        result['violations'].append('Expected 1–4 bullets')
        return result
    settings = json.loads((ROOT/'publishing_v2/design-settings.json').read_text())
    body = settings['typography']['information_bullets']
    sizes = settings['typography']['sizes_px']
    draw = ImageDraw.Draw(Image.new('L', (1, 1)))
    entries = [('headline', draft.get('headline'))] + [('bullet', b) for b in bullets] + [('closing', draft.get('closing'))]
    for role, text in entries:
        f = dict(role=role, text=text, characters=len(text) if isinstance(text, str) else 0)
        result['fields'].append(f)
        if (not isinstance(text, str) or not text.strip() or
                any(unicodedata.category(c).startswith('C') for c in text) or
                not any(unicodedata.category(c)[0] in 'LNPS' for c in text)):
            result['violations'].append(f'{role}: empty or unsupported control text')
            continue
        size = body['size_px'] if role == 'bullet' else sizes[role]
        weight = body['weight_name'] if role == 'bullet' else 'Regular'
        left, right = (70, body['right_anchor_px']) if role == 'bullet' else (60, 1020)
        font = ImageFont.truetype(str(ROOT/f'fonts/Almarai-{weight}.ttf'), size)
        limit = body['maximum_lines'] if role == 'bullet' else 1
        try:
            lines = wrap_text(text, font, draw, left, right)
            f.update(normalized_text=' '.join(text.split()), lines=lines, line_count=len(lines),
                     maximum_lines=limit, remaining_lines=limit-len(lines),
                     remaining_width_px=[right-left-2-(draw.textbbox((0,0),line,font=font,direction='rtl')[2]-draw.textbbox((0,0),line,font=font,direction='rtl')[0]) for line in lines])
            if not lines or len(lines) > limit:
                result['violations'].append(f'{role}: {len(lines)} lines exceeds {limit}')
        except ValueError as exc:
            result['violations'].append(f'{role}: {exc}')
    if result['violations']:
        return result
    # Use the renderer itself for ink heights, distribution and the shared design
    # contract. Blank in-memory pixels are discarded, never exported as a preview.
    from .fixed_information_template import render
    from .bundle_api import BundleError
    try:
        _, blocks = render(draft['headline'], bullets, draft['closing'],
                           [Image.new('RGB', (1, 1))], ['صورة'])
        text_blocks = [b for b in blocks if b['role'] in {'headline','bullet','closing'}]
        for field, block in zip(result['fields'], text_blocks):
            field.update(line_boxes=block['line_boxes'], box=block['box'])
        distribution = settings['information_template']['approved_layout_override']['paragraph_distribution']
        capacity = distribution['bottom_boundary'] - distribution['top_boundary']
        used = sum(b['box'][3]-b['box'][1] for b in text_blocks if b['role']=='bullet')
        result['body_budget'] = dict(height_px=capacity, paragraph_height_px=used,
                                    remaining_height_px=capacity-used,
                                    equal_gap_px=(capacity-used)/(len(bullets)+1))
        result['fit'] = True
    except (ValueError, BundleError) as exc:
        result['violations'].append(str(exc))
    return result


def prepare_text(draft):
    result = measure_card(draft)
    if result['fit']:
        result['receipt'] = _receipt(draft)
        result['display_text'] = '\n\n'.join([draft['headline']] +
            ['• '+b for b in draft['bullets']] + [draft['closing']])
    return result


def receipt_matches(draft, receipt):
    return receipt == _receipt(draft) and measure_card(draft)['fit']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('draft', nargs='?', help='Draft JSON file; omit for stdin')
    parser.add_argument('--display', action='store_true',
                        help='Emit checked text plus the master CTA only on success; JSON to stderr')
    args = parser.parse_args()
    try:
        draft = json.loads(Path(args.draft).read_text(encoding='utf-8')
                           if args.draft else sys.stdin.read())
        result = prepare_text(draft)
        if args.display and result['fit']:
            settings = json.loads((ROOT/'publishing_v2/design-settings.json').read_text())
            cta = settings['editorial_master']['cta_exact']
            if not isinstance(cta, str) or not cta.strip():
                raise ValueError('Missing approved sharing CTA')
            # The fixed CTA belongs to the template; do not rewrite candidate copy.
            result['fixed_cta'] = cta
            result['display_text'] += '\n\n' + cta
    except (OSError, ValueError, KeyError) as exc:
        result = dict(fit=False, violations=[str(exc)])
    print(json.dumps(result, ensure_ascii=False, indent=2),
          file=sys.stderr if args.display else sys.stdout)
    if args.display and result['fit']:
        print(result['display_text'])
    return 0 if result['fit'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
