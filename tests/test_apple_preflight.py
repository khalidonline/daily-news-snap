import copy
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import unittest


class ApplePreflightTests(unittest.TestCase):
    def test_missing_source_and_stale_event_are_blocked_before_render(self):
        import publish_apple_ai_approved as apple
        spec = copy.deepcopy(apple.SPEC)
        spec['attention']['source_url'] = ''
        with self.assertRaises(ValueError): apple.validate_spec(spec, datetime(2026,9,25,tzinfo=timezone.utc))
        with self.assertRaises(ValueError): apple.validate_spec(apple.SPEC, datetime(2026,10,10,tzinfo=timezone.utc))

    def test_wrong_product_and_duplicate_image_are_blocked(self):
        import publish_apple_ai_approved as apple
        spec = copy.deepcopy(apple.SPEC)
        spec['cards'][0]['image']['subject'] = 'iMac'
        with self.assertRaises(ValueError): apple.validate_spec(spec, datetime(2026,9,25,tzinfo=timezone.utc))
        spec = copy.deepcopy(apple.SPEC)
        spec['cards'][1]['image'] = copy.deepcopy(spec['cards'][0]['image'])
        with self.assertRaises(ValueError): apple.validate_spec(spec, datetime(2026,9,25,tzinfo=timezone.utc))

    def test_unreviewed_or_changed_export_cannot_be_published(self):
        import publish_apple_ai_approved as apple
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'manifest.json').write_text('{}')
            with self.assertRaises(ValueError): apple.validate_review(root)


if __name__ == '__main__': unittest.main()
