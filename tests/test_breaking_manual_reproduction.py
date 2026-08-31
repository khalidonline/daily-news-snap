import inspect
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

    def test_confirmed_breaking_pipeline_is_review_only(self):
        watcher_source = inspect.getsource(entry.breaking_watch._watch)
        self.assertIn('POST_TO_SNAPCHAT": "0"', watcher_source)
        self.assertNotIn('POST_TO_SNAPCHAT": "1"', watcher_source)

        workflow = Path(".github/workflows/breaking.yml").read_text(encoding="utf-8")
        self.assertIn('POST_TO_SNAPCHAT: "0"', workflow)

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
