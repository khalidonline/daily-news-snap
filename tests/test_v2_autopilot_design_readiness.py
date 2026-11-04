"""Offline readiness bindings; these tests never run production agents."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from publishing_v2.autopilot import runtime


class DesignReadinessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        paths = ['publishing_v2/autopilot/runtime.py', 'publishing_v2/preview.py',
                 'daily_budget.py', 'news_bot.py', 'story_bot.py', 'requirements.txt',
                 'requirements-v2-images.txt', 'fonts/Almarai-Regular.ttf',
                 'fonts/Almarai-Bold.ttf', 'images/brand/badge.png', 'approved/master/card.png']
        for name in paths:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
        self.settings = self.root / 'publishing_v2/design-settings.json'
        self.settings.write_text(json.dumps({'information_template': {
            'base_artwork_path': 'approved/master/card.png'}}))
        location = patch.object(runtime, '__file__', str(self.root/'publishing_v2/autopilot/runtime.py'))
        location.start()
        self.addCleanup(location.stop)
        environment = patch.dict(runtime.os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def test_design_inputs_invalidate_existing_readiness(self):
        now = datetime(2026, 11, 4, tzinfo=timezone.utc)
        for name in ('publishing_v2/design-settings.json', 'fonts/Almarai-Regular.ttf',
                     'fonts/Almarai-Bold.ttf', 'images/brand/badge.png', 'approved/master/card.png'):
            with self.subTest(name=name):
                old_engine = runtime.engine_id()
                state = {'daily': {'status': 'shadow_passed', 'engine': old_engine, 'at': now.isoformat()}}
                self.assertTrue(runtime.rollout_ready(state, old_engine, now, lane='daily'))
                path = self.root / name
                path.write_bytes(path.read_bytes() + b' ')
                self.assertFalse(runtime.rollout_ready(state, runtime.engine_id(), now, lane='daily'))

    def test_missing_required_asset_fails_closed(self):
        (self.root/'fonts/Almarai-Bold.ttf').unlink()
        with self.assertRaises(FileNotFoundError):
            runtime.engine_id()

    def test_outside_master_artwork_path_is_rejected(self):
        self.settings.write_text(json.dumps({'information_template': {'base_artwork_path': '../outside.png'}}))
        with self.assertRaisesRegex(ValueError, 'design_asset_outside_repository'):
            runtime.engine_id()

    def test_symlink_artwork_escape_is_rejected_before_read(self):
        path = self.root/'approved/master/card.png'
        path.unlink()
        path.symlink_to(self.root.parent/'not-a-real-artwork.png')
        with self.assertRaisesRegex(ValueError, 'design_asset_outside_repository'):
            runtime.engine_id()

    def test_missing_artwork_fails_closed(self):
        (self.root/'approved/master/card.png').unlink()
        with self.assertRaises(FileNotFoundError):
            runtime.engine_id()

    def test_malformed_master_fails_closed(self):
        self.settings.write_text('{broken')
        with self.assertRaises(json.JSONDecodeError):
            runtime.engine_id()

    def test_master_artwork_selection_changes_identity(self):
        before = runtime.engine_id()
        (self.root/'approved/master/other.png').write_bytes(b'different artwork')
        self.settings.write_text(json.dumps({'information_template': {
            'base_artwork_path': 'approved/master/other.png'}}))
        self.assertNotEqual(before, runtime.engine_id())

    def test_engine_is_deterministic(self):
        self.assertEqual(runtime.engine_id(), runtime.engine_id())

    def test_model_changes_still_invalidate_engine(self):
        before = runtime.engine_id()
        with patch.dict(runtime.os.environ, {'AUTOPILOT_WRITER_MODEL': 'different'}):
            self.assertNotEqual(before, runtime.engine_id())
