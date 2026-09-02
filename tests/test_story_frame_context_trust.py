import json
import tempfile
import unittest
from pathlib import Path

import runtime_relevance as rr


class StoryFrameContextTrustTests(unittest.TestCase):
    def selected_local(self, source_name):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        selected = Path(td.name) / "story-frame.jpg"
        selected.write_bytes(b"selected")
        Path(str(selected) + ".exempt").write_text(
            f"local:{source_name}", encoding="utf-8"
        )
        return selected

    def ledger(self, assets):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        path = Path(td.name) / "relevance.json"
        path.write_text(json.dumps({"assets": assets}), encoding="utf-8")
        return path

    def test_unreviewed_curated_cross_entity_asset_cannot_bypass_frame_gate(self):
        selected = self.selected_local("targeted-careem-dammam-airport.jpg")
        ledger = self.ledger({})
        self.assertFalse(
            rr.explicitly_trusted_selected_local_visual(
                selected,
                "قصة سكة حديد الرياض الدمام 1951",
                ledger,
            )
        )

    def test_unreviewed_mcdonalds_asset_cannot_bypass_railway_frame_gate(self):
        selected = self.selected_local("mcdonalds-riyadh-2009.jpg")
        ledger = self.ledger({})
        self.assertFalse(
            rr.explicitly_trusted_selected_local_visual(
                selected,
                "قصة سكة حديد الرياض الدمام 1951",
                ledger,
            )
        )

    def test_explicit_story_review_still_allows_documentary_bypass(self):
        source = "targeted-sama-1953-10-riyal.jpg"
        selected = self.selected_local(source)
        ledger = self.ledger({
            source: {
                "stories": {"قصة تأسيس مؤسسة النقد ساما": rr.STRONG_CONTEXT}
            }
        })
        self.assertTrue(
            rr.explicitly_trusted_selected_local_visual(
                selected,
                "قصة تأسيس مؤسسة النقد ساما",
                ledger,
            )
        )


if __name__ == "__main__":
    unittest.main()
