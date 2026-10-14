import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from publishing_v2.readability import validate_readability, ReadabilityError

class ReadabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / 'card.jpg'
        Image.new('RGB', (1080, 1920), 'white').save(self.image)
        self.media = [(self.image, self.image.read_bytes())]
        self.report = {'version': 1, 'visual_review': {'approved': True, 'reference': 'Khalid reviewed mobile preview'},
            'cards': [{'sha256': hashlib.sha256(self.media[0][1]).hexdigest(),
                'headline': {'text': 'طاري اليوم', 'size': 52, 'box': [82, 300, 998, 380]},
                'bullets': [{'text': 'معلومة واضحة ومختصرة', 'size': 48, 'box': [82, 950, 956, 1090]}],
                'cta': {'text': 'شاركها مع صديقك اللي تعجبه هذي المعلومة', 'size': 38, 'box': [82, 1650, 890, 1770]}}]}
    def check(self):
        path = self.root / 'readability.json'
        path.write_text(json.dumps(self.report))
        validate_readability(path, self.media)
    def test_valid_card(self): self.check()
    def test_challenge_uses_one_closing_without_information_cta(self):
        card = self.report['cards'][0]
        card['layout'] = 'visual_challenge'
        del card['cta']
        card['closing'] = {'text': 'لقيته؟ خلّ خويك يجرّب', 'size': 43, 'box': [82, 1510, 992, 1570]}
        self.check()
    def test_information_still_requires_cta(self):
        del self.report['cards'][0]['cta']
        with self.assertRaises(ReadabilityError): self.check()
    def test_challenge_rejects_duplicate_cta(self):
        card = self.report['cards'][0]
        card['layout'] = 'visual_challenge'
        card['closing'] = {'text': 'لقيته؟ خلّ خويك يجرّب', 'size': 43, 'box': [82, 1510, 992, 1570]}
        with self.assertRaises(ReadabilityError): self.check()
    def test_reject_small_body_and_cta(self):
        for section, size in [('bullets', 45), ('cta', 32)]:
            with self.subTest(section=section):
                target = self.report['cards'][0][section]
                if isinstance(target, list): target = target[0]
                old = target['size']; target['size'] = size
                with self.assertRaises(ReadabilityError): self.check()
                target['size'] = old
    def test_reject_four_bullets(self):
        self.report['cards'][0]['bullets'] *= 4
        with self.assertRaises(ReadabilityError): self.check()
    def test_reject_changed_image(self):
        self.report['cards'][0]['sha256'] = '0' * 64
        with self.assertRaises(ReadabilityError): self.check()
    def test_reject_headline_wrap_without_shrinking(self):
        self.report['cards'][0]['headline']['text'] = 'عنوان طويل جدًا ' * 12
        with self.assertRaises(ReadabilityError): self.check()
    def test_reject_overlapping_boxes(self):
        self.report['cards'][0]['cta']['box'] = [82, 950, 956, 1100]
        with self.assertRaises(ReadabilityError): self.check()
    def test_reject_long_bullet(self):
        self.report['cards'][0]['bullets'][0]['text'] *= 12
        with self.assertRaises(ReadabilityError): self.check()
    def test_visual_review_required(self):
        self.report['visual_review']['approved'] = False
        with self.assertRaises(ReadabilityError): self.check()

class OptionalIntroTests(unittest.TestCase):
    check = ReadabilityTests.check
    def setUp(self):
        ReadabilityTests.setUp(self)
        self.report['typography_profile'] = 'owner-bold40-20261008'
        c = self.report['cards'][0]
        c['cta']['size'] = 40
        c['cta']['text'] = 'شاركها مع صديقك اللي تعجبه المعلومة'
        c['closing'] = {'text': 'خاتمة واضحة', 'size': 40, 'box': [82, 1450, 998, 1520]}
    def test_optional_intro_can_be_absent(self):
        self.check()
    def test_present_intro_still_rejects_small_font(self):
        self.report['cards'][0]['intro'] = {'text': 'مقدمة', 'size': 26, 'box': [82, 600, 998, 660]}
        with self.assertRaises(ReadabilityError): self.check()
    def test_present_intro_still_rejects_overlap(self):
        self.report['cards'][0]['intro'] = {'text': 'مقدمة', 'size': 40, 'box': [82, 950, 998, 1090]}
        with self.assertRaises(ReadabilityError): self.check()

class DeliveryGateTests(unittest.TestCase):
    def test_empty_receipt_does_not_bypass_gate(self):
        from publishing_v2.readability import require_for_new_delivery
        with self.assertRaises(ReadabilityError):
            require_for_new_delivery('missing/manifest.json', [('card', b'bytes')], {'1': {}})
    def test_reconciliation_does_not_require_new_render(self):
        from publishing_v2.readability import require_for_new_delivery
        require_for_new_delivery('missing/manifest.json', [('card', b'bytes')],
                                 {'1': {'status': 'SENDING', 'post_id': 'existing-id'}})
    def test_partial_delivery_still_checks_new_cards(self):
        from publishing_v2.readability import require_for_new_delivery
        with self.assertRaises(ReadabilityError):
            require_for_new_delivery('missing/manifest.json', [('a', b'a'), ('b', b'b')],
                                     {'1': {'status': 'POSTED', 'post_id': 'existing-id'}})
    def test_cli_blocks_before_upload_without_report(self):
        from unittest.mock import patch, MagicMock
        from publishing_v2 import bundle_api as b
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / 'manifest.json'
            manifest.write_text('{}')
            client, journal = MagicMock(), MagicMock()
            journal.read.return_value = {}
            with patch('sys.argv', ['bundle_api', 'publish', '--manifest', str(manifest)]), \
                 patch.object(b, 'load_package', return_value=('identity', 'title', [('card', b'bytes')])), \
                 patch.object(b, 'BundleClient', return_value=client), \
                 patch.object(b, 'GitHubJournal', return_value=journal), \
                 patch.object(b, 'publish') as publish:
                with self.assertRaises(SystemExit): b.main()
                publish.assert_not_called()
                client.upload.assert_not_called()
