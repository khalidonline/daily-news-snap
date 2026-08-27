import json
import tempfile
import unittest
from pathlib import Path

from tools.bulk_visual_board import CoverageRow
from tools.bulk_visual_curation import write_curation
from tools.bulk_visual_history import FailureHistory, remember


class FailureHistoryTests(unittest.TestCase):
    def test_rejected_ids_are_suppressed_but_acceptance_is_not_cached(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "history.json"
            remember({"story": "S", "source_id": "commons:1", "result": "WRONG_ENTITY"}, path)
            remember({"story": "S", "source_id": "commons:2", "result": "ACCEPTED"}, path)
            history = FailureHistory("S", json.loads(path.read_text())["records"])
            self.assertEqual(history.rejected_source_ids, {"commons:1"})

    def test_exhaustion_is_query_specific_so_changed_query_falls_through(self):
        history = FailureHistory("S", [{"story": "S", "source": "commons", "beat": "origin",
            "query": "Exact old query", "result": "NO_SAFE_CANDIDATE"}])
        self.assertTrue(history.query_exhausted("commons", "origin", ("Exact old query",)))
        self.assertFalse(history.query_exhausted("commons", "origin", ("Exact new context",)))

    def test_curation_is_deterministic_and_bounded(self):
        row = CoverageRow("Unknown", (), (), 1, True, "NEEDS")
        records = [{"story": "Unknown", "source": "commons", "source_id": f"commons:{i}",
                    "query": f"q{i}", "reason": "x" * 500} for i in range(40)]
        with tempfile.TemporaryDirectory() as td:
            one, two = Path(td) / "one.json", Path(td) / "two.json"
            write_curation([row], one, records); write_curation([row], two, records)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            entry = json.loads(one.read_text())["entries"][0]
            self.assertLessEqual(len(entry["rejected_candidates"]), 16)
            self.assertLessEqual(len(entry["queries_attempted"]), 24)
            self.assertEqual(entry["deficit"], {"photos": 1, "logo": 1})
