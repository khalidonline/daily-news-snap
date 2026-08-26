import json
import tempfile
import unittest
from pathlib import Path

from runtime_relevance import (
    DIRECT,
    STRONG_CONTEXT,
    WEAK_GENERIC,
    WRONG_ENTITY,
    asset_countable,
    runtime_status,
)


class RuntimeRelevanceTests(unittest.TestCase):
    def write_ledger(self, data):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        path = Path(td.name) / "relevance.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_unreviewed_materialized_asset_does_not_count(self):
        ledger = self.write_ledger({"assets": {}})
        self.assertFalse(asset_countable("rt-jack-bogle-2.jpg", "Jack Bogle", ledger))

    def test_manually_curated_asset_counts_by_default(self):
        ledger = self.write_ledger({"assets": {}})
        self.assertTrue(asset_countable("jack-bogle.jpg", "Jack Bogle", ledger))

    def test_only_direct_and_strong_context_verdicts_count(self):
        ledger = self.write_ledger({
            "assets": {
                "a.jpg": {"stories": {"Story A": DIRECT}},
                "b.jpg": {"stories": {"Story A": STRONG_CONTEXT}},
                "c.jpg": {"stories": {"Story A": WEAK_GENERIC}},
                "d.jpg": {"stories": {"Story A": WRONG_ENTITY}},
            }
        })
        self.assertTrue(asset_countable("a.jpg", "Story A", ledger))
        self.assertTrue(asset_countable("b.jpg", "Story A", ledger))
        self.assertFalse(asset_countable("c.jpg", "Story A", ledger))
        self.assertFalse(asset_countable("d.jpg", "Story A", ledger))

    def test_story_specific_verdict_does_not_leak_to_other_story(self):
        ledger = self.write_ledger({
            "assets": {
                "rt-shared.jpg": {"stories": {"Story A": DIRECT}}
            }
        })
        self.assertTrue(asset_countable("rt-shared.jpg", "Story A", ledger))
        self.assertFalse(asset_countable("rt-shared.jpg", "Story B", ledger))

    def test_pass_requires_four_photos_and_logo(self):
        self.assertEqual(runtime_status(4, 1), "PASS")
        self.assertEqual(runtime_status(3, 1), "NEEDS 1 MORE PHOTO")
        self.assertEqual(runtime_status(4, 0), "NEEDS LOGO")
        self.assertEqual(runtime_status(2, 0), "NEEDS 2 MORE PHOTOS + LOGO")


if __name__ == "__main__":
    unittest.main()
