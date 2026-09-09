import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import breaking_watch_entry as entry


EVENT = (
    "وزير خارجية تركيا يعلن بدء تشكيل الهيكل الأساسي لاتفاق مكة الدفاعي "
    "بين السعودية وتركيا وباكستان"
)


class ManualBreakingReproductionTests(unittest.TestCase):
    @mock.patch.dict(
        os.environ,
        {"CONFIRMED_BREAKING_EVENT": "", "TRIGGER_CONFIRMED_EVENT": EVENT},
        clear=False,
    )
    @mock.patch.object(entry.breaking_watch, "watch")
    @mock.patch.object(entry.subprocess, "call", return_value=0)
    def test_trigger_file_confirmed_event_bypasses_classifier(self, call, watch):
        rc = entry.run()

        self.assertEqual(0, rc)
        watch.assert_not_called()
        self.assertEqual(EVENT, call.call_args.kwargs["env"]["PINNED_EVENT"])

    @mock.patch.dict(os.environ, {"CONFIRMED_BREAKING_EVENT": EVENT}, clear=False)
    @mock.patch.object(entry.breaking_watch, "watch")
    @mock.patch.object(entry.subprocess, "call", return_value=0)
    def test_confirmed_event_bypasses_watcher_and_forces_dry_run(
        self, call, watch
    ):
        rc = entry.run()

        self.assertEqual(rc, 0)
        watch.assert_not_called()
        call.assert_called_once()
        command = call.call_args.args[0]
        env = call.call_args.kwargs["env"]
        self.assertEqual(command, [entry.sys.executable, "breaking_resilient_runner.py"])
        self.assertEqual(env["PINNED_EVENT"], EVENT)
        self.assertEqual(env["DRY_RUN"], "1")
        self.assertEqual(env["POST_TO_SNAPCHAT"], "0")

    @mock.patch.object(entry.subprocess, "call", return_value=0)
    def test_strict_runner_forces_review_only_even_if_caller_requests_post(self, call):
        entry._run_strict_news_bot({
            "PINNED_EVENT": EVENT,
            "POST_TO_SNAPCHAT": "1",
        })

        env = call.call_args.kwargs["env"]
        self.assertEqual(env["POST_TO_SNAPCHAT"], "0")

    def test_breaking_workflow_is_review_only(self):
        workflow = Path(".github/workflows/breaking.yml").read_text(encoding="utf-8")
        self.assertIn('DRY_RUN: "1"', workflow)
        self.assertIn('POST_TO_SNAPCHAT: "0"', workflow)
        self.assertIn("github.event.client_payload.confirmed_event", workflow)
        self.assertIn("types: [breaking-recovery]", workflow)

    @mock.patch.dict(os.environ, {"CONFIRMED_BREAKING_EVENT": ""}, clear=False)
    @mock.patch.object(entry.breaking_watch, "watch")
    @mock.patch.object(entry.subprocess, "call")
    def test_normal_entry_still_runs_watcher(self, call, watch):
        rc = entry.run()

        self.assertEqual(rc, 0)
        watch.assert_called_once_with()
        call.assert_not_called()

    @mock.patch.dict(os.environ, {"CONFIRMED_BREAKING_EVENT": EVENT, "BREAKING_RUN_MODE": "repair_visual"}, clear=False)
    @mock.patch.object(entry.breaking_watch, "watch")
    @mock.patch.object(entry.subprocess, "call", return_value=0)
    def test_manual_recovery_passes_cache_first_mode_to_runner(self, call, watch):
        entry.run()
        watch.assert_not_called()
        self.assertEqual("repair_visual", call.call_args.kwargs["env"]["BREAKING_RUN_MODE"])

    @mock.patch.dict(os.environ, {"CONFIRMED_BREAKING_EVENT": EVENT}, clear=False)
    @mock.patch.object(entry.breaking_watch, "save_state")
    @mock.patch.object(entry.breaking_watch, "load_state")
    @mock.patch.object(entry.breaking_watch, "ksa_now")
    @mock.patch.object(entry.subprocess, "call")
    def test_manual_recovery_skips_event_already_delivered_today(
        self, call, ksa_now, load_state, save_state
    ):
        now = datetime(2026, 9, 9, 21, 0, tzinfo=timezone.utc)
        ksa_now.return_value = now
        load_state.return_value = {
            "date": now.date().isoformat(),
            "event_fp": entry.breaking_watch.event_fp(EVENT),
            "reviewed": True,
            "stamps": ["earlier-delivery"],
        }

        self.assertEqual(0, entry.run())

        call.assert_not_called()
        save_state.assert_not_called()

    @mock.patch.dict(os.environ, {"CONFIRMED_BREAKING_EVENT": EVENT}, clear=False)
    @mock.patch.object(entry.breaking_watch, "ksa_stamp", return_value="delivery-stamp")
    @mock.patch.object(entry.breaking_watch, "save_state")
    @mock.patch.object(entry.breaking_watch, "load_state")
    @mock.patch.object(entry.breaking_watch, "ksa_now")
    @mock.patch.object(entry.subprocess, "call", return_value=0)
    def test_successful_manual_recovery_records_review_delivery(
        self, call, ksa_now, load_state, save_state, _ksa_stamp
    ):
        now = datetime(2026, 9, 9, 21, 0, tzinfo=timezone.utc)
        ksa_now.return_value = now
        load_state.return_value = {
            "date": now.date().isoformat(),
            "event_fp": entry.breaking_watch.event_fp(EVENT),
            "reviewed": False,
            "stamps": [],
        }

        self.assertEqual(0, entry.run())

        call.assert_called_once()
        saved = save_state.call_args.args[0]
        self.assertTrue(saved["reviewed"])
        self.assertEqual(saved["event_fp"], entry.breaking_watch.event_fp(EVENT))
        self.assertEqual(saved["stamps"], ["delivery-stamp"])
        self.assertEqual(saved["lock_at"], "")

    def test_workflow_defaults_manual_runs_to_visual_repair(self):
        workflow = Path(".github/workflows/breaking.yml").read_text(encoding="utf-8")
        for mode in ("repair_visual", "regenerate_editorial", "new_event"):
            self.assertIn(mode, workflow)


if __name__ == "__main__":
    unittest.main()
