#!/usr/bin/env python3
"""Owner review in chat: print a saved package's text and re-render its exact cards.

Reads the sealed shadow journal from the public snapchat-api-state branch (git only),
and loads the review sheet the workflow saved from the exact sealed cards (no model
calls, no publishing, no image downloads).
Usage: python review_package.py [daily|local|<slot>] [output-dir]
"""
import base64, json, subprocess, sys
from pathlib import Path


def journal(name):
    subprocess.run(['git', 'fetch', '-q', 'origin', 'snapchat-api-state'], check=True)
    raw = subprocess.run(['git', 'show', f'origin/snapchat-api-state:api-receipts/{name}.json'],
                         check=True, capture_output=True).stdout
    return json.loads(raw)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'daily'
    out = Path(sys.argv[2] if len(sys.argv) > 2 else 'review-output')
    slot = journal('autopilot-readiness')[which]['slot'] if which in ('daily', 'local') else which
    state = journal(slot)
    package = state['package']
    print(f'slot: {slot}\nstatus: {state["status"]}  expires: {package.get("expires_at")}\n'
          f'title: {package["title"]}\n')
    for i, card in enumerate(package['cards']):
        if card.get('kind') == 'credits':
            continue
        print(f'[{i + 1}] {card["kind"]}: {card["title"]}\n    {card["body"]}\n    ◀ {card.get("punch")}'
              + (f'\n    صورة: {card.get("image_caption")}' if card.get('image_caption') else ''))
    out.mkdir(parents=True, exist_ok=True)
    try:
        sheet = journal('review-sheet-' + slot)
    except subprocess.CalledProcessError:
        print('\nno review sheet saved for this slot (text only)'); return
    sealed = state.get('approval', {}).get('media_sha256', [])
    if sheet.get('media_sha256') != sealed:
        print('\nreview sheet does NOT match the sealed package; do not approve from it'); return
    target = out / (slot + '.jpg')
    target.write_bytes(base64.b64decode(sheet['jpeg_b64']))
    print(f'\nreview sheet ({len(sealed)} sealed cards, right-to-left): {target}')

if __name__ == '__main__':
    main()
