import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from publishing_v2.autopilot import review_sheet


def package(root, lane='daily', cid='c1', n=3):
    folder = Path(root) / lane / cid / 'current'; folder.mkdir(parents=True)
    hashes = []
    for i in range(n):
        path = folder / f'card-{i:02d}.jpg'
        Image.new('RGB', (1080, 1920), (40 * i, 80, 120)).save(path, 'JPEG')
        hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
    return {'lane': lane, 'status': 'shadow_passed', 'candidate_id': cid, 'slot': f'slot-{lane}',
            'media_sha256': hashes, 'title': 'قصة'}


class Store:
    saved = {}
    def __init__(self, name): self.name = name
    def save(self, data): Store.saved[self.name] = data


class ReviewSheetTests(unittest.TestCase):
    def setUp(self): Store.saved = {}

    def run_main(self, root, results, mode='shadow', review='1'):
        Path(root, 'summary.json').write_text(json.dumps({'mode': mode, 'results': results}))
        with patch.dict('os.environ', {'AUTOPILOT_OWNER_REVIEW': review}):
            return review_sheet.main(root, journal=Store)

    def test_saves_sheet_only_for_sealed_unchanged_cards(self):
        with tempfile.TemporaryDirectory() as root:
            good, bad = package(root), package(root, lane='local', cid='c2')
            Path(root, 'local', 'c2', 'current', 'card-01.jpg').write_bytes(b'changed')
            held = {'lane': 'daily', 'status': 'held', 'slot': 'x'}
            self.assertEqual(self.run_main(root, [good, bad, held]), 0)
            self.assertEqual(list(Store.saved), ['review-sheet-slot-daily'])
            row = Store.saved['review-sheet-slot-daily']
            self.assertEqual(row['media_sha256'], good['media_sha256'])
            import base64, io
            with Image.open(io.BytesIO(base64.b64decode(row['jpeg_b64']))) as sheet:
                self.assertEqual(sheet.size, (3 * 360 + 2 * 12, 640))

    def test_off_or_live_stores_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            row = package(root)
            self.run_main(root, [row], review='0')
            self.run_main(root, [row], mode='live')
            self.assertEqual(Store.saved, {})

    def test_first_card_is_rightmost(self):
        with tempfile.TemporaryDirectory() as root:
            row = package(root)
            paths = review_sheet.verified_cards(row, root)
            import io
            with Image.open(io.BytesIO(review_sheet.build_sheet(paths))) as sheet:
                right = sheet.getpixel((sheet.width - 10, 10)); left = sheet.getpixel((10, 10))
            self.assertLess(right[0], 20)      # card 0 is (0, 80, 120)
            self.assertGreater(left[0], 60)    # card 2 is (80, 80, 120)


class WesternDigitsTests(unittest.TestCase):
    def test_card_text_uses_western_digits_without_mutating_source(self):
        from publishing_v2.autopilot.runtime import western_digits
        card = {'kind': 'story', 'title': 'عام ١٩٩٩', 'body': 'بين ٢٠٠٧ و۲۰۱۲، M5 بذاكرة 512',
                'punch': 'نزل يوم ٢٤ سبتمبر', 'image_caption': 'لقطة ٢٠١٤', 'image': {'sha256': '٠'}}
        out = western_digits(card)
        self.assertEqual(out['title'], 'عام 1999')
        self.assertEqual(out['body'], 'بين 2007 و2012، M5 بذاكرة 512')
        self.assertEqual(out['punch'], 'نزل يوم 24 سبتمبر')
        self.assertEqual(out['image_caption'], 'لقطة 2014')
        self.assertEqual(card['title'], 'عام ١٩٩٩')
        self.assertIs(out['image'], card['image'])
