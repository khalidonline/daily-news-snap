import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
import tempfile

from tools.bulk_visual_board import CoverageRow
from tools.bulk_visual_repair import _download, catalogue_photo_paths, process_rows, repair_photos


def row(story, need_photos, need_logo, status):
    return CoverageRow(story, tuple(), tuple(), need_photos, need_logo, status)


class BulkVisualRepairTests(unittest.TestCase):
    @patch("tools.bulk_visual_repair.urlopen")
    def test_commons_download_retries_429_once_and_caches_by_source_id(self, open_url):
        error = HTTPError("https://upload.wikimedia.org/thumb/x.jpg", 429, "rate", {}, None)
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"image bytes"
        open_url.side_effect = [error, response]
        candidate = SimpleNamespace(source="commons", source_id="commons:unique-test",
                                    direct_url="https://upload.wikimedia.org/thumb/x.jpg")
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "one", Path(directory) / "two"
            _download(candidate, first, sleep=lambda _: None)
            _download(candidate, second, sleep=lambda _: None)
            self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(open_url.call_count, 2)

    @patch("tools.bulk_visual_repair.plan_story_beats")
    @patch("tools.bulk_visual_repair.catalogue_photo_paths", return_value=[])
    @patch("tools.bulk_visual_repair.sb.story_logo_domain", return_value=None)
    @patch("tools.bulk_visual_repair.discover_openverse", return_value=[])
    @patch("tools.bulk_visual_repair.discover_loc", return_value=[])
    @patch("tools.bulk_visual_repair.discover_commons")
    def test_discovery_receives_seen_ids_and_does_not_log_repeat_as_duplicate(
            self, commons, _loc, _openverse, _domain, _catalogue, beats):
        from tools.bulk_visual_sources import SourceCandidate, StoryBeat
        beat_one = StoryBeat("one", ("NVIDIA origin",), ("NVIDIA",))
        beat_two = StoryBeat("two", ("NVIDIA modern",), ("NVIDIA",))
        beats.return_value = [beat_one, beat_two]
        def candidate(source_id):
            return SourceCandidate("commons", source_id, "https://commons.test/page",
                "https://upload.test/image.jpg", "unproven", "unproven", "", "", "",
                800, 600, "one", "NVIDIA", ("NVIDIA",), ())
        def discover(_beat, _limit, *, excluded_source_ids):
            return [candidate("commons:1")] if "commons:1" not in excluded_source_ids else []
        commons.side_effect = discover
        attempts = []
        repair_photos("NVIDIA story", 1, attempt_fn=attempts.append)
        duplicate_repeats = [row for row in attempts if row.get("result") == "DUPLICATE_ONLY"
                             and "source_id already evaluated" in row.get("reason", "")]
        self.assertEqual(duplicate_repeats, [])
        self.assertEqual(commons.call_args_list[1].kwargs["excluded_source_ids"], {"commons:1"})

    @patch("tools.bulk_visual_repair.build_board")
    def test_dedupe_catalogue_includes_relevant_photos_from_every_story(self, board):
        board.return_value = [
            CoverageRow("One", ("one.jpg",), (), 3, True, "NEEDS"),
            CoverageRow("Two", ("two.jpg",), (), 3, True, "NEEDS"),
        ]
        self.assertEqual(catalogue_photo_paths(),
                         [__import__("pathlib").Path("images/one.jpg"),
                          __import__("pathlib").Path("images/two.jpg")])

    def test_one_story_failure_does_not_abort_next_story(self):
        calls, attempts = [], []
        def photos(story, deficit):
            calls.append(story)
            if story == "Broken":
                raise RuntimeError("source down")
            return 1
        result = process_rows(
            [row("Broken", 1, False, "NEEDS"), row("Good", 1, False, "NEEDS")], 2,
            lambda story: 0, photos, lambda story: row(story, 1, False, "NEEDS"), attempts.append,
        )
        self.assertEqual(calls, ["Broken", "Good"])
        self.assertEqual(result.progress, 0)
        self.assertEqual(attempts[0]["result"], "SOURCE_UNAVAILABLE")
        self.assertEqual(result.exit_code, 3)

    def test_pass_story_is_skipped_without_attempt_writes(self):
        called = []
        result = process_rows(
            [row("Done", 0, False, "PASS")], 1,
            lambda story: called.append("logo") or 1,
            lambda story, deficit: called.append("photo") or 1,
            lambda story: row(story, 0, False, "PASS"), called.append,
        )
        self.assertEqual(called, [])
        self.assertEqual(result.progress, 0)

    def test_logo_runs_before_photo_for_same_story(self):
        calls = []
        process_rows(
            [row("Mixed", 1, True, "NEEDS")], 1,
            lambda story: calls.append("logo") or 1,
            lambda story, deficit: calls.append("photo") or 1,
            lambda story: row(story, 1, False, "NEEDS"), lambda record: None,
        )
        self.assertEqual(calls, ["logo", "photo"])

    def test_zero_progress_returns_no_progress_exit(self):
        result = process_rows(
            [row("Blocked", 1, True, "NEEDS")], 1, lambda story: 0,
            lambda story, deficit: 0, lambda story: row(story, 1, True, "NEEDS"),
            lambda record: None,
        )
        self.assertEqual(result.exit_code, 2)

    def test_runtime_coverage_rejecting_a_claimed_write_is_invariant_error(self):
        result = process_rows(
            [row("Invisible", 1, False, "NEEDS")], 1, lambda story: 0,
            lambda story, deficit: 1, lambda story: row(story, 1, False, "NEEDS"),
            lambda record: None,
        )
        self.assertEqual(result.exit_code, 3)
        self.assertEqual(result.progress, 0)

    def test_two_claimed_writes_for_one_runtime_slot_is_invariant_error(self):
        result = process_rows(
            [row("Overclaimed", 2, False, "NEEDS")], 1, lambda story: 0,
            lambda story, deficit: 2, lambda story: row(story, 1, False, "NEEDS"),
            lambda record: None,
        )
        self.assertEqual(result.exit_code, 3)
        self.assertEqual(result.progress, 1)

    def test_logo_and_photo_reductions_are_counted_from_final_runtime_row(self):
        states = iter((row("Mixed", 1, False, "NEEDS"), row("Mixed", 0, False, "PASS")))
        result = process_rows(
            [row("Mixed", 1, True, "NEEDS")], 1, lambda story: 1,
            lambda story, deficit: 1, lambda story: next(states), lambda record: None,
        )
        self.assertEqual((result.progress, result.exit_code), (2, 0))

    def test_progress_with_runtime_deficit_reduction_returns_ten(self):
        result = process_rows(
            [row("Improved", 2, False, "NEEDS")], 1, lambda story: 0,
            lambda story, deficit: 1, lambda story: row(story, 1, False, "NEEDS"),
            lambda record: None,
        )
        self.assertEqual((result.progress, result.exit_code), (1, 10))


if __name__ == "__main__":
    unittest.main()
