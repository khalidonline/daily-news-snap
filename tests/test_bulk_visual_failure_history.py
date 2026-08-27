import tempfile
import unittest
from pathlib import Path

from tools.bulk_visual_failure_history import (
    empty_history, load_history, mark_query_set_complete, query_set_complete,
    query_set_fingerprint, record_attempt, rejected_source_ids, save_history,
)


class DurableFailureHistoryTests(unittest.TestCase):
    def test_deterministic_rejection_survives_a_second_controller_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            first = empty_history()
            record_attempt(first, {"story": "S", "source": "commons",
                                   "source_id": "commons:7", "result": "IDENTITY_UNPROVEN",
                                   "reason": "explicit incompatible identity"})
            save_history(first, path)
            self.assertEqual(rejected_source_ids(load_history(path), "S"), {"commons:7"})

    def test_accepted_is_never_durable_approval(self):
        history = empty_history()
        record_attempt(history, {"story": "S", "source_id": "commons:1",
                                 "result": "ACCEPTED", "reason": "reviewed"})
        self.assertEqual(history, empty_history())

    def test_transient_failures_and_conflicts_do_not_complete_queries(self):
        history = empty_history(); fingerprint = query_set_fingerprint(("one", "two"))
        for result in ("SOURCE_DISCOVERY_BUDGET_EXCEEDED", "SOURCE_RATE_LIMITED",
                       "SOURCE_UNAVAILABLE", "DISCOVERY_ENTITY_CONFLICT_SKIPPED"):
            record_attempt(history, {"story": "S", "beat": "B", "source": "commons",
                                     "result": result, "reason": "retryable diagnostic"})
        self.assertFalse(query_set_complete(history, "S", "B", "commons", fingerprint))

    def test_complete_query_set_is_fingerprint_specific(self):
        history = empty_history(); old = query_set_fingerprint(("one", "two"))
        mark_query_set_complete(history, "S", "B", "commons", old)
        self.assertTrue(query_set_complete(history, "S", "B", "commons", old))
        self.assertFalse(query_set_complete(
            history, "S", "B", "commons", query_set_fingerprint(("one", "three"))))

    def test_history_is_bounded_and_contains_no_runtime_coverage_field(self):
        history = empty_history()
        for number in range(550):
            record_attempt(history, {"story": "S", "result": "SOURCE_UNAVAILABLE",
                                     "reason": str(number)})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"; save_history(history, path)
            loaded = load_history(path)
        self.assertEqual(len(loaded["diagnostics"]), 500)
        self.assertNotIn("coverage", loaded)


if __name__ == "__main__":
    unittest.main()
