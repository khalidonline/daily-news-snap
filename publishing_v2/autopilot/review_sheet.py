"""Owner-review phase: save a compact review sheet of each passed package.

The owner reviews text and images in chat. This step stores one downscaled sheet
per passed lane on the state branch, next to the sealed journal, so a reviewer
with git access can see the exact cards without artifacts, API access or
Telegram. Cards are hash-checked against the approval seal first; a changed or
missing card stores nothing for that lane. No model calls, no publishing.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path

from PIL import Image

CARD_WIDTH = 360          # 1080x1920 cards at one third: text stays legible, sheet ~150 KB
GAP = 12


def verified_cards(row, root):
    hashes, candidate = row.get('media_sha256') or [], row.get('candidate_id')
    if row.get('status') != 'shadow_passed' or not hashes or not candidate:
        return None
    folder = Path(root) / row['lane'] / candidate / 'current'
    paths = [folder / f'card-{i:02d}.jpg' for i in range(len(hashes))]
    if all(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in zip(paths, hashes)):
        return paths
    return None


def build_sheet(paths):
    frames = []
    for path in paths:
        with Image.open(path) as im:
            im = im.convert('RGB')
            frames.append(im.resize((CARD_WIDTH, round(im.height * CARD_WIDTH / im.width))))
    height = max(f.height for f in frames)
    # Right-to-left, like the story plays for an Arabic reader.
    sheet = Image.new('RGB', (len(frames) * CARD_WIDTH + (len(frames) - 1) * GAP, height), 'white')
    for i, frame in enumerate(frames):
        sheet.paste(frame, (sheet.width - (i + 1) * CARD_WIDTH - i * GAP, 0))
    buffer = io.BytesIO()
    sheet.save(buffer, 'JPEG', quality=82, optimize=True)
    return buffer.getvalue()


def main(root='autopilot-output', journal=None):
    if os.environ.get('AUTOPILOT_OWNER_REVIEW', '').strip() != '1':
        print('Owner review phase off'); return 0
    summary_path = Path(root) / 'summary.json'
    if not summary_path.exists():
        print('No summary'); return 0
    summary = json.loads(summary_path.read_text())
    if summary.get('mode') != 'shadow':
        return 0
    if journal is None:
        from publishing_v2.bundle_api import GitHubJournal as journal
    for row in summary.get('results', []):
        paths = verified_cards(row, root)
        if paths is None:
            if row.get('status') == 'shadow_passed':
                print('Review sheet skipped, cards missing or changed: ' + str(row.get('lane')))
            continue
        store = journal('review-sheet-' + row['slot'])
        store.save({'slot': row['slot'], 'lane': row['lane'], 'title': row.get('title'),
                    'media_sha256': row['media_sha256'],
                    'jpeg_b64': base64.b64encode(build_sheet(paths)).decode()})
        print('Review sheet saved: ' + row['slot'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
