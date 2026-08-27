import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from runtime_relevance import DIRECT, WEAK_GENERIC, WRONG_ENTITY
from tools.bulk_visual_sources import SourceCandidate
from tools.bulk_visual_validate import VisualDuplicateIndex, validate_candidate


def make_image(path, fmt="JPEG"):
    # A continuous-tone background keeps the fixture photo-like rather than a
    # three-colour illustration.
    image = Image.new("RGB", (640, 480))
    draw = ImageDraw.Draw(image)
    for y in range(480):
        colour = (30 + y * 173 // 479, 50 + y * 139 // 479, 80 + y * 101 // 479)
        draw.line((0, y, 639, y), fill=colour)
    draw.rectangle((60, 60, 300, 420), fill=(80, 100, 120))
    draw.ellipse((330, 90, 590, 350), fill=(170, 120, 90))
    image.save(path, fmt)


def candidate(title="Jack Bogle", description="John C. Bogle at Vanguard"):
    return SourceCandidate(
        source="commons", source_id="commons:1",
        source_page="https://commons.wikimedia.org/wiki/File:Bogle.jpg",
        direct_url="https://upload.wikimedia.org/bogle.jpg", title=title,
        description=description, creator="Bill Cramer", license="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        width=640, height=480, beat_key="person", matched_on="Jack Bogle",
        required_identity=("Jack Bogle", "John C. Bogle"), depicts=("John C. Bogle",),
    )


class BulkVisualValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.download_source = self.root / "download.jpg"
        make_image(self.download_source)
        self.download = lambda cand, dest: shutil.copy2(self.download_source, dest)

    def test_wrong_entity_never_accepts(self):
        result = validate_candidate("Jack Bogle story", candidate(), [], self.root, lambda *args: WRONG_ENTITY, self.download)
        self.assertFalse(result.accepted); self.assertEqual(result.verdict, WRONG_ENTITY)

    def test_weak_generic_never_accepts(self):
        result = validate_candidate("Jack Bogle story", candidate(), [], self.root, lambda *args: WEAK_GENERIC, self.download)
        self.assertFalse(result.accepted)

    def test_structured_rejection_verdicts_never_accept(self):
        for verdict in (WEAK_GENERIC, WRONG_ENTITY):
            reviewer = lambda *args, verdict=verdict: {
                "verdict": verdict, "reason": "not suitable",
                "source_metadata_sufficient": True,
            }
            with self.subTest(verdict=verdict):
                result = validate_candidate(
                    "Jack Bogle story", candidate(), [], self.root, reviewer, self.download)
                self.assertFalse(result.accepted)
                self.assertEqual(result.verdict, verdict)

    def test_exact_duplicate_never_accepts(self):
        existing = self.root / "existing.jpg"; shutil.copy2(self.download_source, existing)
        result = validate_candidate("Jack Bogle story", candidate(), [existing], self.root, lambda *args: DIRECT, self.download)
        self.assertFalse(result.accepted); self.assertIn("duplicate", result.reason.lower())

    def test_perceptual_duplicate_never_accepts(self):
        existing = self.root / "existing.png"; make_image(existing, "PNG")
        result = validate_candidate("Jack Bogle story", candidate(), [existing], self.root, lambda *args: DIRECT, self.download)
        self.assertFalse(result.accepted); self.assertIn("duplicate", result.reason.lower())

    def test_person_candidate_requires_source_metadata_identity(self):
        cand = candidate(title="Vanguard office", description="Vanguard headquarters")
        cand = cand.__class__(**{**cand.__dict__, "depicts": tuple()})
        result = validate_candidate("Jack Bogle story", cand, [], self.root, lambda *args: DIRECT, self.download)
        self.assertFalse(result.accepted); self.assertIn("identity", result.reason.lower())

    def test_unproven_identity_is_rejected_without_fetch_or_model_review(self):
        cand = candidate(title="Generic office", description="An office")
        cand = cand.__class__(**{**cand.__dict__, "depicts": tuple()})
        calls = []
        result = validate_candidate(
            "Jack Bogle story", cand, [], self.root,
            lambda *args: calls.append("model") or DIRECT,
            lambda *args: calls.append("fetch"),
        )
        self.assertFalse(result.accepted)
        self.assertEqual(calls, [])
        self.assertIn("identity", result.phase_seconds)

    def test_prebuilt_duplicate_index_avoids_rehashing_catalogue_per_candidate(self):
        existing = self.root / "existing.jpg"; shutil.copy2(self.download_source, existing)
        index = VisualDuplicateIndex.from_paths([existing])
        # The supplied path is deliberately invalid: validation must use the
        # already-built run index rather than walking the catalogue again.
        result = validate_candidate(
            "Jack Bogle story", candidate(), [self.root / "missing.jpg"], self.root,
            lambda *args: DIRECT, self.download, index,
        )
        self.assertFalse(result.accepted)
        self.assertIn("duplicate", result.reason.lower())

    def test_every_person_story_beat_requires_source_metadata_identity(self):
        cand = candidate(title="Vanguard office", description="Vanguard headquarters")
        cand = cand.__class__(**{**cand.__dict__, "beat_key": "legacy", "depicts": tuple()})
        result = validate_candidate("Jack Bogle story", cand, [], self.root, lambda *args: DIRECT, self.download)
        self.assertFalse(result.accepted); self.assertIn("identity", result.reason.lower())

    def test_non_person_candidate_requires_independent_source_identity(self):
        cand = candidate(title="Modern headquarters", description="A large office building")
        cand = cand.__class__(**{**cand.__dict__, "beat_key": "modern_result",
                                "required_identity": ("NVIDIA",), "depicts": tuple()})
        result = validate_candidate("NVIDIA story", cand, [], self.root,
                                    lambda *args: DIRECT, self.download)
        self.assertFalse(result.accepted)
        self.assertIn("identity", result.reason.lower())

    def test_non_person_source_identity_allows_model_review(self):
        cand = candidate(title="NVIDIA headquarters", description="NVIDIA campus")
        cand = cand.__class__(**{**cand.__dict__, "beat_key": "modern_result",
                                "required_identity": ("NVIDIA",), "depicts": tuple()})
        result = validate_candidate("NVIDIA story", cand, [], self.root,
                                    lambda *args: DIRECT, self.download)
        self.assertTrue(result.accepted)

    def test_flat_graphic_cannot_enter_photo_pool(self):
        graphic = self.root / "graphic.png"
        image = Image.new("RGB", (640, 480), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((100, 100, 540, 380), fill=(20, 80, 180))
        draw.rectangle((180, 180, 460, 300), fill=(255, 220, 20))
        image.save(graphic)
        download = lambda cand, dest: shutil.copy2(graphic, dest)
        result = validate_candidate("Jack Bogle story", candidate(), [], self.root, lambda *args: DIRECT, download)
        self.assertFalse(result.accepted); self.assertIn("graphic", result.reason.lower())

    def test_direct_candidate_accepts_after_local_decode(self):
        result = validate_candidate("Jack Bogle story", candidate(), [], self.root, lambda *args: DIRECT, self.download)
        self.assertTrue(result.accepted); self.assertEqual(result.verdict, DIRECT)
        self.assertTrue(result.temp_path.exists())
