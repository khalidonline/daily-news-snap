import os
import tempfile
import unittest

import story_cost_guard as scg


class TransportReservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved_root = os.environ.get("STORY_COST_STATE_ROOT")
        os.environ["STORY_COST_STATE_ROOT"] = self.tmp.name

    def tearDown(self):
        if self.saved_root is None:
            os.environ.pop("STORY_COST_STATE_ROOT", None)
        else:
            os.environ["STORY_COST_STATE_ROOT"] = self.saved_root
        self.tmp.cleanup()

    def test_zero_charge_transport_failure_releases_reservation(self):
        first = scg.reserve_editorial_call("story", "rev", "auto")
        scg.record_model_result(
            first,
            model="claude-sonnet-5",
            message_id=None,
            input_tokens=0,
            output_tokens=0,
            web_search_requests=0,
            status="transport_error",
        )

        second = scg.reserve_editorial_call("story", "rev", "auto")
        self.assertEqual(first.guard_revision, second.guard_revision)

    def test_error_after_a_response_keeps_reservation_locked(self):
        first = scg.reserve_editorial_call("story", "rev", "auto")
        scg.record_model_result(
            first,
            model="claude-sonnet-5",
            message_id="msg_1",
            input_tokens=10,
            output_tokens=0,
            web_search_requests=0,
            status="error",
        )

        with self.assertRaises(scg.EditorialSpendBlocked):
            scg.reserve_editorial_call("story", "rev", "auto")

    def test_generic_error_without_usage_keeps_reservation_locked(self):
        first = scg.reserve_editorial_call("story", "rev", "auto")
        scg.record_model_result(
            first,
            model="claude-sonnet-5",
            message_id=None,
            input_tokens=0,
            output_tokens=0,
            web_search_requests=0,
            status="error",
        )

        with self.assertRaises(scg.EditorialSpendBlocked):
            scg.reserve_editorial_call("story", "rev", "auto")


if __name__ == "__main__":
    unittest.main()
