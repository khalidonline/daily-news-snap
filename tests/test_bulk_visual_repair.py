import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from io import BytesIO
import json
import os
import tempfile

from tools.bulk_visual_board import CoverageRow
from tools.bulk_visual_repair import (
    _download, _strict_relevance, catalogue_photo_paths, process_rows, repair_photos,
)
from tools.bulk_visual_validate import ReviewerConfigurationError
import tools.bulk_visual_repair as repair


def row(story, need_photos, need_logo, status):
    return CoverageRow(story, tuple(), tuple(), need_photos, need_logo, status)


class BulkVisualRepairTests(unittest.TestCase):
    def setUp(self):
        repair._REVIEWER_CONFIGURATION_FAILURE = None

    def reviewer_candidate(self):
        return SimpleNamespace(title="Title", description="Description", depicts="Entity",
                               beat_key="beat")

    def http_error(self, status, error_type="invalid_request_error", message="bad request"):
        body = json.dumps({"type": "error", "error": {"type": error_type,
                                                        "message": message}}).encode()
        return HTTPError("https://api.anthropic.com/v1/messages", status, "error", {},
                         BytesIO(body))

    def call_reviewer(self, open_url, telemetry, directory, **kwargs):
        image = Path(directory) / "image.png"
        from PIL import Image
        Image.new("RGB", (4, 4)).save(image)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-secret",
                                    "VISION_MODEL": "configured-model"}, clear=False), \
                patch("tools.bulk_visual_repair.urlopen", open_url):
            return _strict_relevance("Exact story", self.reviewer_candidate(), image,
                                     telemetry_fn=telemetry.append, sleep=lambda _: None,
                                     **kwargs)

    def test_reviewer_successful_response(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = BytesIO(json.dumps({"content": [{"type": "text", "text":
            '{"verdict":"DIRECT","reason":"matches","source_metadata_sufficient":true}'}]}).encode())
        with tempfile.TemporaryDirectory() as directory:
            result = self.call_reviewer(unittest.mock.Mock(return_value=response), [], directory)
        self.assertEqual(result["verdict"], "DIRECT")

    def test_reviewer_requests_anthropic_structured_output(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = BytesIO(json.dumps({"content": [{"type": "text", "text":
            '{"verdict":"DIRECT","reason":"matches","source_metadata_sufficient":true}'}]}).encode())
        open_url = unittest.mock.Mock(return_value=response)
        with tempfile.TemporaryDirectory() as directory:
            self.call_reviewer(open_url, [], directory)
        payload = json.loads(open_url.call_args.args[0].data)
        output_format = payload["output_config"]["format"]
        self.assertEqual(output_format["type"], "json_schema")
        schema = output_format["schema"]
        self.assertEqual(schema["properties"]["verdict"]["enum"],
                         ["DIRECT", "STRONG_CONTEXT", "WEAK_GENERIC", "WRONG_ENTITY"])
        self.assertEqual(set(schema["required"]),
                         {"verdict", "reason", "source_metadata_sufficient"})
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(payload["model"], "configured-model")
        self.assertEqual(payload["max_tokens"], 300)

    def test_reviewer_401_and_403_fail_fast(self):
        for status in (401, 403):
            open_url, telemetry = unittest.mock.Mock(side_effect=self.http_error(status)), []
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(HTTPError):
                self.call_reviewer(open_url, telemetry, directory)
            self.assertEqual(open_url.call_count, 1)
            self.assertFalse(telemetry[0]["retryable"])
            self.assertEqual(telemetry[0]["failure_category"],
                             "authentication" if status == 401 else "permission")

    def test_reviewer_invalid_model_client_error_fails_fast(self):
        error = self.http_error(404, "not_found_error",
                                "model: claude-sonnet-4-20250514")
        open_url, telemetry = unittest.mock.Mock(side_effect=error), []
        with tempfile.TemporaryDirectory() as directory, \
                self.assertRaises(ReviewerConfigurationError):
            self.call_reviewer(open_url, telemetry, directory)
        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(telemetry[0]["api_error_type"], "not_found_error")
        self.assertEqual(telemetry[0]["model"], "configured-model")
        self.assertEqual(telemetry[0]["failure_category"], "invalid_model")

    def test_invalid_model_short_circuits_subsequent_reviews(self):
        error = self.http_error(404, "not_found_error",
                                "model: claude-sonnet-4-20250514")
        open_url, telemetry = unittest.mock.Mock(side_effect=error), []
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ReviewerConfigurationError):
                self.call_reviewer(open_url, telemetry, directory)
            with self.assertRaises(ReviewerConfigurationError):
                self.call_reviewer(open_url, telemetry, directory)
        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(len(telemetry), 1)

    def test_invalid_reviewer_configuration_aborts_batch(self):
        calls = []
        def photos(story, _deficit):
            calls.append(story)
            raise ReviewerConfigurationError("invalid reviewer model")
        with self.assertRaises(ReviewerConfigurationError):
            process_rows(
                [row("First", 1, False, "NEEDS"), row("Second", 1, False, "NEEDS")], 2,
                lambda story: 0, photos, lambda story: row(story, 1, False, "NEEDS"),
                lambda record: None,
            )
        self.assertEqual(calls, ["First"])

    def test_reviewer_429_retry_is_bounded(self):
        open_url, telemetry = unittest.mock.Mock(side_effect=lambda *_args, **_kwargs:
                                                  (_ for _ in ()).throw(self.http_error(429,
                                                      "rate_limit_error", "limited"))), []
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(HTTPError):
            self.call_reviewer(open_url, telemetry, directory)
        self.assertEqual(open_url.call_count, 3)
        self.assertTrue(all(item["retryable"] for item in telemetry))
        self.assertTrue(all(item["failure_category"] == "rate_limit" for item in telemetry))

    def test_reviewer_5xx_retry_is_bounded(self):
        open_url, telemetry = unittest.mock.Mock(side_effect=lambda *_args, **_kwargs:
                                                  (_ for _ in ()).throw(self.http_error(503,
                                                      "api_error", "unavailable"))), []
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(HTTPError):
            self.call_reviewer(open_url, telemetry, directory)
        self.assertEqual(open_url.call_count, 3)
        self.assertTrue(all(item["failure_category"] == "anthropic_service"
                            for item in telemetry))

    def test_malformed_model_response_fails_closed(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = BytesIO(b'{"content":[{"type":"text","text":"not json"}]}')
        telemetry = []
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(json.JSONDecodeError):
            self.call_reviewer(unittest.mock.Mock(return_value=response), telemetry, directory)
        self.assertEqual(telemetry[0]["failure_category"], "invalid_reviewer_output_json")
        self.assertNotIn("not json", json.dumps(telemetry))

    def test_invalid_envelope_json_has_distinct_bounded_telemetry(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = BytesIO(b'{not envelope json')
        telemetry = []
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(json.JSONDecodeError):
            self.call_reviewer(unittest.mock.Mock(return_value=response), telemetry, directory)
        self.assertEqual(telemetry[0]["failure_category"], "invalid_response_envelope_json")
        self.assertNotIn("not envelope", json.dumps(telemetry))

    def test_unexpected_response_envelope_fails_closed(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = BytesIO(b'{"content":{"type":"text"}}')
        telemetry = []
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            self.call_reviewer(unittest.mock.Mock(return_value=response), telemetry, directory)
        self.assertEqual(telemetry[0]["failure_category"], "invalid_reviewer_output_schema")

    def test_missing_or_unexpected_fields_fail_closed(self):
        outputs = (
            '{"verdict":"DIRECT","reason":"matches"}',
            '{"verdict":"DIRECT","reason":"matches","source_metadata_sufficient":true,"extra":1}',
        )
        for output in outputs:
            response = unittest.mock.MagicMock()
            response.__enter__.return_value = BytesIO(json.dumps(
                {"content": [{"type": "text", "text": output}]}).encode())
            telemetry = []
            with self.subTest(output=output), tempfile.TemporaryDirectory() as directory, \
                    self.assertRaises(ValueError):
                self.call_reviewer(unittest.mock.Mock(return_value=response), telemetry, directory)
            self.assertEqual(telemetry[0]["failure_category"], "invalid_reviewer_output_schema")

    def test_markdown_fenced_output_is_not_stripped_or_reparsed(self):
        output = '```json\n{"verdict":"DIRECT","reason":"matches","source_metadata_sufficient":true}\n```'
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = BytesIO(json.dumps(
            {"content": [{"type": "text", "text": output}]}).encode())
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(json.JSONDecodeError):
            self.call_reviewer(unittest.mock.Mock(return_value=response), [], directory)

    def test_reviewer_telemetry_never_exposes_api_key(self):
        error = self.http_error(400, "invalid_request_error", "bad sk-test-secret credential")
        telemetry = []
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(HTTPError):
            self.call_reviewer(unittest.mock.Mock(side_effect=error), telemetry, directory)
        self.assertNotIn("sk-test-secret", json.dumps(telemetry))
        self.assertIn("[REDACTED]", telemetry[0]["api_error_message"])

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
