import tempfile, unittest
from pathlib import Path
from importlib.util import find_spec
from unittest.mock import patch

class SavedTests(unittest.TestCase):
    def test_changed_saved_card_blocks_publication(self):
        self.assertIsNotNone(find_spec('publishing_v2.saved_owner_package'))
        from publishing_v2.saved_owner_package import save_reviewed, publish_saved
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'card.jpg'; p.write_bytes(b'approved pixels')
            manifest=save_reviewed({'title':'test','expires_at':'2099-01-01T00:00:00Z'},[p],Path(d))
            p.write_bytes(b'changed')
            with patch('publishing_v2.autopilot.runtime.publish_package') as send:
                with self.assertRaises(ValueError): publish_saved(manifest,'test')
                send.assert_not_called()
    def test_missing_manifest_never_prepares(self):
        self.assertIsNotNone(find_spec('publishing_v2.saved_owner_package'))
        from publishing_v2.saved_owner_package import publish_saved
        with self.assertRaises((ValueError,FileNotFoundError)):
            publish_saved(Path('/nonexistent/package.json'),'test')

if __name__=='__main__': unittest.main()
