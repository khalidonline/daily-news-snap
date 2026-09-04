import os
import unittest
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
        self.assertEqual(command, [entry.sys.executable, "breaking_news_runner.py"])
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
        self.assertIn("TRIGGER_CONFIRMED_EVENT", workflow)
        self.assertIn("PINNED_EVENT_URL", workflow)

    @mock.patch.dict(os.environ, {"CONFIRMED_BREAKING_EVENT": ""}, clear=False)
    @mock.patch.object(entry.breaking_watch, "watch")
    @mock.patch.object(entry.subprocess, "call")
    def test_normal_entry_still_runs_watcher(self, call, watch):
        rc = entry.run()

        self.assertEqual(rc, 0)
        watch.assert_called_once_with()
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
