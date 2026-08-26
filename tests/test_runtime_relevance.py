import json
import tempfile
import unittest
from pathlib import Path

import runtime_relevance as rr
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


class RuntimePhotoContractTests(unittest.TestCase):
    def test_bogle_shape_consumes_approved_photos_before_text_or_extra_logo(self):
        self.assertTrue(
            hasattr(rr, "runtime_contract_slots"),
            "runtime photo contract planner is not implemented yet",
        )
        brief = {
            "frames": [
                {"subject_kind": "company"},
                {"subject_kind": "person"},
                {"subject_kind": "company"},
                {"subject_kind": "abstract"},
                {"subject_kind": "company"},
                {"subject_kind": "abstract"},
            ]
        }
        # Mirrors the observed Bogle run: logo, approved portrait, text,
        # text, logo, text. Three unused approved photos must land on 1/3/4.
        selected = ["logo-1", "approved-portrait", None, None, "logo-5", None]
        approved_flags = [False, True, False, False, False, False]
        logo_flags = [True, False, False, False, True, False]
        slots = rr.runtime_contract_slots(
            brief, selected, approved_flags, logo_flags, target=4
        )
        self.assertEqual(slots, [0, 2, 3])

    def test_contract_preserves_a_sole_logo_when_other_slots_can_take_photos(self):
        self.assertTrue(
            hasattr(rr, "runtime_contract_slots"),
            "runtime photo contract planner is not implemented yet",
        )
        brief = {
            "frames": [
                {"subject_kind": "company"},
                {"subject_kind": "person"},
                {"subject_kind": "company"},
                {"subject_kind": "company"},
                {"subject_kind": "company"},
                {"subject_kind": "abstract"},
            ]
        }
        selected = ["only-logo", "approved-portrait", None, None, None, None]
        approved_flags = [False, True, False, False, False, False]
        logo_flags = [True, False, False, False, False, False]
        slots = rr.runtime_contract_slots(
            brief, selected, approved_flags, logo_flags, target=4
        )
        self.assertEqual(slots, [2, 3, 4])


if __name__ == "__main__":
    unittest.main()
