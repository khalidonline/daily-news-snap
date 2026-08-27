import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.bulk_visual_board import CoverageRow
from tools.bulk_visual_curation import write_curation
from tools.bulk_visual_failure_history import (
    empty_history, load_history, sanitize_history,
)
from tools.bulk_visual_queue import build_run_queue
from tools.bulk_visual_repair import append_attempt, process_rows
from tools.bulk_visual_sources import StoryBeat
from tools.bulk_visual_strategy import story_source_strategy


def row(story, need_photos, need_logo, status="NEEDS"):
    return CoverageRow(story, tuple(), tuple(), need_photos, need_logo, status)


class FinalVisualConvergenceTests(unittest.TestCase):
    def test_sanitize_history_drops_non_catalogue_records_only(self):
        history = {
            "version": 1,
            "candidate_rejections": [
                {"story": "Real", "source_id": "commons:1", "result": "IDENTITY_UNPROVEN"},
                {"story": "NVIDIA story", "source_id": "commons:test", "result": "IDENTITY_UNPROVEN"},
            ],
            "complete_query_sets": [
                {"story": "Real", "beat": "origin", "source": "commons", "fingerprint": "real"},
                {"story": "NVIDIA story", "beat": "one", "source": "loc", "fingerprint": "fake"},
            ],
            "diagnostics": [
                {"story": "Real", "result": "SOURCE_UNAVAILABLE"},
                {"story": "NVIDIA story", "result": "SOURCE_UNAVAILABLE"},
            ],
        }
        clean = sanitize_history(history, {"Real"})
        self.assertEqual({item["story"] for item in clean["candidate_rejections"]}, {"Real"})
        self.assertEqual({item["story"] for item in clean["complete_query_sets"]}, {"Real"})
        self.assertEqual({item["story"] for item in clean["diagnostics"]}, {"Real"})

    def test_append_attempt_can_use_isolated_history_path(self):
        production = Path("state/bulk_visual_failure_history.json")
        before = production.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            attempts = Path(directory) / "attempts.jsonl"
            history_path = Path(directory) / "history.json"
            append_attempt({
                "story": "S", "kind": "photo", "source": "commons",
                "result": "SOURCE_UNAVAILABLE", "reason": "temporary outage",
            }, path=attempts, history_path=history_path)
            self.assertEqual(len(load_history(history_path)["diagnostics"]), 1)
        self.assertEqual(production.read_bytes(), before)

    def test_near_pass_queue_orders_logo_then_one_photo_then_mixed(self):
        rows = [row("Large", 3, True), row("Mixed", 1, True),
                row("Photo", 1, False), row("Logo", 0, True)]
        queue = build_run_queue(rows, {"photo-needed": None, "logo-only": None}, 12)
        self.assertEqual([item.story for item in queue], ["Logo", "Photo", "Mixed", "Large"])

    def test_logo_only_process_never_calls_photo_repair(self):
        photo_calls = []
        result = process_rows(
            [row("Logo", 0, True)], 1,
            lambda story: 0,
            lambda story, deficit: photo_calls.append((story, deficit)) or 0,
            lambda story: row(story, 0, True),
            lambda record: None,
        )
        self.assertEqual(photo_calls, [])
        self.assertEqual(result.progress, 0)

    def test_story_source_strategy_uses_typed_context(self):
        person = [StoryBeat("person", ("Ada Lovelace photograph",), ("Ada Lovelace",), "person")]
        company = [StoryBeat("origin", ("Acme founding",), ("Acme",), "entity", ("company",))]
        gulf_company = [StoryBeat("origin", ("Acme Saudi founding",), ("Acme",),
                                  "entity", ("company", "saudi"))]
        historical = [StoryBeat("origin", ("Event history",), ("Event",),
                                "entity", ("history",))]
        product = [StoryBeat("origin", ("Widget invention",), ("Widget",),
                             "entity", ("invention",))]
        fallback = [StoryBeat("origin", ("Subject detail",), ("Subject",), "entity")]
        with patch("tools.bulk_visual_strategy.sb.story_logo_domain", side_effect=lambda story: {
                "Person": None, "Company": "company.example", "Gulf": "gulf.example",
                "History": None, "Product": None, "Fallback": None}[story]):
            self.assertEqual(story_source_strategy("Person", person),
                             ("commons", "loc", "first-party", "openverse"))
            self.assertEqual(story_source_strategy("Company", company),
                             ("first-party", "commons", "openverse", "loc"))
            self.assertEqual(story_source_strategy("Gulf", gulf_company),
                             ("first-party", "commons", "loc", "openverse"))
            self.assertEqual(story_source_strategy("History", historical),
                             ("commons", "loc", "openverse", "first-party"))
            self.assertEqual(story_source_strategy("Product", product),
                             ("commons", "first-party", "loc", "openverse"))
            self.assertEqual(story_source_strategy("Fallback", fallback),
                             ("commons", "loc", "openverse", "first-party"))

    def test_curation_contains_full_bounded_history_evidence(self):
        rows = [row("S", 2, True), row("Done", 0, False, "PASS")]
        history = empty_history()
        history["candidate_rejections"] = [{
            "story": "S", "source": "commons", "source_id": "commons:1",
            "result": "IDENTITY_UNPROVEN",
        }]
        history["diagnostics"] = [{
            "story": "S", "beat": "origin", "source": "commons",
            "source_id": "commons:1", "result": "IDENTITY_UNPROVEN",
            "reason": "wrong identity",
        }]
        history["complete_query_sets"] = [{
            "story": "S", "beat": "origin", "source": "commons", "fingerprint": "fp",
        }]
        beat = StoryBeat("origin", ("S history",), ("S",), "entity", ("history",), ())
        with tempfile.TemporaryDirectory() as directory, \
                patch("tools.bulk_visual_curation.plan_story_beats", return_value=[beat]), \
                patch("tools.bulk_visual_curation.story_source_strategy",
                      return_value=("commons", "loc", "openverse", "first-party")):
            path = Path(directory) / "curation.json"
            write_curation(rows, history, path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 1)
        self.assertEqual(len(payload["entries"]), 1)
        entry = payload["entries"][0]
        self.assertEqual(entry["story"], "S")
        self.assertEqual(entry["deficit"], {"photos": 2, "logo": 1})
        self.assertEqual(entry["required_identity"], {
            "type": "entity", "aliases": ["S"], "context": ["history"],
            "incompatible_senses": [],
        })
        self.assertEqual(entry["missing_beats"], ["origin"])
        self.assertEqual(entry["completed_query_sets"], [
            {"beat": "origin", "source": "commons", "fingerprint": "fp"}
        ])
        self.assertEqual(entry["rejected_candidates"], [{
            "source_id": "commons:1", "source": "commons",
            "result": "IDENTITY_UNPROVEN", "reason": "wrong identity",
        }])
        self.assertIn("verified logo identity", entry["constraints"])
        self.assertEqual(entry["recommended_source"],
                         "commons then loc then openverse then first-party")

    def test_curation_write_does_not_mutate_coverage_rows(self):
        rows = [row("S", 1, True)]
        before = tuple(rows)
        beat = StoryBeat("origin", ("S history",), ("S",), "entity", ("history",), ())
        with tempfile.TemporaryDirectory() as directory, \
                patch("tools.bulk_visual_curation.plan_story_beats", return_value=[beat]), \
                patch("tools.bulk_visual_curation.story_source_strategy", return_value=("commons",)):
            write_curation(rows, empty_history(), Path(directory) / "curation.json")
        self.assertEqual(tuple(rows), before)


if __name__ == "__main__":
    unittest.main()
