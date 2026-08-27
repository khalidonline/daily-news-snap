import subprocess
import unittest
from unittest.mock import Mock, patch

from tools.bulk_visual_board import CoverageRow
import tools.bulk_visual_run as runner


def row(story, need_photos, need_logo, status="NEEDS"):
    return CoverageRow(story, tuple(), tuple(), need_photos, need_logo, status)


class BulkVisualRunCliTests(unittest.TestCase):
    @patch.object(runner, "run_bounded", return_value=10)
    def test_cli_forwards_bounded_workflow_options(self, run_bounded):
        rc = runner.main([
            "--max-stories", "7",
            "--max-candidates-per-beat", "9",
            "--story-timeout-seconds", "140",
            "--soft-deadline-seconds", "1200",
        ])
        self.assertEqual(rc, 10)
        run_bounded.assert_called_once_with(
            max_stories=7,
            max_candidates=9,
            story_timeout_seconds=140,
            soft_deadline_seconds=1200,
        )


class BulkVisualRunProbeTests(unittest.TestCase):
    @patch.object(runner.sb, "load_stories")
    @patch.object(runner, "build_board")
    def test_runtime_row_reloads_story_metadata(self, board, load_stories):
        expected = row("Story", 0, False, "PASS")
        board.return_value = [expected]
        self.assertEqual(runner.runtime_row("Story"), expected)
        load_stories.assert_called_once_with()
        board.assert_called_once_with(["Story"])

    @patch.object(runner, "_spawn_story_process")
    @patch.object(runner, "runtime_row")
    def test_timeout_is_labeled_and_post_coverage_is_still_measured(self, runtime_row, spawn):
        proc = Mock()
        proc.wait.side_effect = subprocess.TimeoutExpired("repair", 150)
        proc.poll.return_value = None
        spawn.return_value = proc
        runtime_row.return_value = row("Hard", 1, False)
        result = runner.run_story_probe(row("Hard", 1, False), 12, timeout_seconds=150)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.result, "TIME_BUDGET_EXCEEDED")
        self.assertEqual(result.after_gap, 1)

    @patch.object(runner, "_git")
    def test_restore_visual_worktree_restores_tracked_and_removes_attempt_untracked(self, git):
        runner.restore_visual_worktree()
        self.assertEqual(git.call_args_list[0].args[0], [
            "restore", "--source=HEAD", "--staged", "--worktree", "--", "images", "stories.txt",
            "state/bulk_visual_failure_history.json",
        ])
        self.assertEqual(git.call_args_list[1].args[0], ["clean", "-fd", "--", "images"])

    @patch.object(runner.os, "killpg")
    @patch.object(runner, "_spawn_story_process")
    @patch.object(runner, "runtime_row")
    def test_timeout_terminates_the_story_process_group(self, runtime_row, spawn, killpg):
        proc = Mock(pid=321)
        proc.wait.side_effect = [subprocess.TimeoutExpired("repair", 150), None]
        proc.poll.return_value = None
        spawn.return_value = proc
        runtime_row.return_value = row("Hard", 1, False)
        runner.run_story_probe(row("Hard", 1, False), 12, timeout_seconds=150)
        killpg.assert_called()

    @patch.object(runner.os, "killpg")
    def test_sigkill_timeout_path_reaps_child_and_tolerates_missing_group(self, killpg):
        proc = Mock(pid=321)
        proc.wait.side_effect = [subprocess.TimeoutExpired("repair", 5), None]
        killpg.side_effect = [None, ProcessLookupError()]
        runner._terminate_process_group(proc)
        self.assertEqual(proc.wait.call_count, 2)

    @patch.object(runner, "visual_worktree_status", return_value=["?? images/leftover.jpg"])
    def test_runner_refuses_preexisting_visual_dirt(self, status):
        with self.assertRaisesRegex(RuntimeError, "visual worktree must be clean"):
            runner.assert_clean_visual_worktree()


class BulkVisualRunControllerTests(unittest.TestCase):
    def test_controller_hard_clamps_story_limit_to_twelve(self):
        with patch.object(runner, "assert_clean_visual_worktree"), patch.object(
            runner, "build_board", return_value=[]
        ), patch.object(runner, "load_cursor", return_value={}), patch.object(
            runner, "build_run_queue", return_value=[]
        ) as build_queue:
            runner._initial_and_queue(999)
        self.assertEqual(build_queue.call_args.args[2], 12)

    def test_full_board_regression_detects_unrelated_story_loss(self):
        accepted = [row("Target", 1, False), row("Other", 0, False, "PASS")]
        candidate = [row("Target", 0, False, "PASS"), row("Other", 1, False)]
        self.assertEqual(runner.board_regressions(accepted, candidate), ["Other"])

    def test_timeout_progress_is_decided_only_by_runtime_gap(self):
        progress = runner.ProbeResult(
            "Partial", "photo-needed", 2, 1, 124, 150.0, True,
            "TIME_BUDGET_EXCEEDED",
        )
        stuck = runner.ProbeResult(
            "Stuck", "photo-needed", 1, 1, 124, 150.0, True,
            "TIME_BUDGET_EXCEEDED",
        )
        self.assertTrue(runner.has_safe_progress(progress))
        self.assertFalse(runner.has_safe_progress(stuck))

    @patch.object(runner, "run_story_probe")
    @patch.object(runner, "validate_checkpoint")
    @patch.object(runner, "commit_checkpoint")
    def test_safe_progress_is_checkpointed_before_next_probe(
        self, checkpoint, validate, probe
    ):
        first, second = row("First", 1, False), row("Second", 1, False)
        probe.side_effect = [
            runner.ProbeResult("First", "photo-needed", 1, 0, 10, 1, False, "SAFE_PROGRESS"),
            runner.ProbeResult("Second", "photo-needed", 1, 1, 2, 1, False, "NO_PROGRESS"),
        ]
        with patch.object(runner, "_initial_and_queue", return_value=([first, second], [first, second], {"photo-needed": None, "logo-only": None})), patch.object(runner, "_final_board", return_value=[first, second]), patch.object(runner, "restore_visual_worktree"), patch.object(runner, "write_summary"):
            runner.run_bounded(max_stories=2)
        validate.assert_called_once_with()
        self.assertTrue(checkpoint.call_args_list[0].kwargs["visual_progress"])
        self.assertLess(validate.call_args_list[0], checkpoint.call_args_list[0])

    @patch.object(runner, "run_story_probe")
    @patch.object(runner, "commit_checkpoint")
    def test_full_board_regression_rolls_back_without_checkpoint(self, checkpoint, probe):
        target = row("Target", 1, False)
        other = row("Other", 0, False, "PASS")
        probe.return_value = runner.ProbeResult(
            "Target", "photo-needed", 1, 0, 10, 1, False, "SAFE_PROGRESS"
        )
        regressed = [row("Target", 0, False, "PASS"), row("Other", 1, False)]
        with patch.object(
            runner, "_initial_and_queue",
            return_value=([target, other], [target], {"photo-needed": None, "logo-only": None}),
        ), patch.object(runner, "_final_board", side_effect=[regressed, [target, other]]), patch.object(
            runner, "restore_visual_worktree"
        ) as restore, patch.object(runner, "write_summary"):
            self.assertEqual(runner.run_bounded(max_stories=1), 3)
        restore.assert_called_once_with()
        checkpoint.assert_not_called()

    @patch.object(runner, "run_story_probe")
    @patch.object(runner, "commit_checkpoint")
    def test_invariant_does_not_advance_or_checkpoint_cursor(self, checkpoint, probe):
        item = row("Bad", 1, False)
        probe.return_value = runner.ProbeResult("Bad", "photo-needed", 1, 1, 3, 1, False, "INVARIANT")
        with patch.object(runner, "_initial_and_queue", return_value=([item], [item], {"photo-needed": None, "logo-only": None})), patch.object(runner, "_final_board", return_value=[item]), patch.object(runner, "restore_visual_worktree"), patch.object(runner, "write_summary"):
            self.assertEqual(runner.run_bounded(max_stories=1), 3)
        checkpoint.assert_not_called()

    @patch.object(runner, "run_story_probe")
    @patch.object(runner, "commit_checkpoint")
    def test_curation_artifact_uses_complete_final_unresolved_board(self, checkpoint, probe):
        first, second, untouched = (row("First", 1, False), row("Second", 1, False),
                                    row("Untouched", 1, True))
        probe.side_effect = [
            runner.ProbeResult("First", "photo-needed", 1, 1, 2, 1, False, "NO_PROGRESS"),
            runner.ProbeResult("Second", "photo-needed", 1, 1, 2, 1, False, "NO_PROGRESS"),
        ]
        with patch.object(
            runner, "_initial_and_queue",
            return_value=([first, second, untouched], [first, second],
                          {"photo-needed": None, "logo-only": None}),
        ), patch.object(runner, "_final_board", return_value=[first, second, untouched]), \
                patch.object(runner, "restore_visual_worktree"), \
                patch.object(runner, "_write_unresolved") as write_curation, \
                patch.object(runner, "write_summary"):
            runner.run_bounded(max_stories=2)
        self.assertEqual(write_curation.call_args.args[0], [first, second, untouched])
        self.assertEqual(write_curation.call_args.args[1],
                         runner.OUT_DIR / "curation-required.json")

    @patch.object(runner, "time")
    def test_soft_deadline_reserves_story_budget(self, fake_time):
        fake_time.monotonic.side_effect = [0, 1490]
        item = row("Late", 1, False)
        with patch.object(runner, "_initial_and_queue", return_value=([item], [item], {"photo-needed": None, "logo-only": None})), patch.object(runner, "run_story_probe") as probe, patch.object(runner, "commit_checkpoint"), patch.object(runner, "_final_board", return_value=[item]), patch.object(runner, "write_summary"):
            runner.run_bounded(max_stories=1, soft_deadline_seconds=1500)
        probe.assert_not_called()
