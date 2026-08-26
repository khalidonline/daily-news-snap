import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from tools.bulk_visual_register import (
    LogoIdentityConflict,
    RegistrationInvariantError,
    add_logo_domain_to_story_text,
    append_index_line,
    deterministic_photo_name,
    merge_logo_aliases,
    merge_relevance_entry,
    register_logo,
    register_photo,
)
import tools.bulk_visual_register as registration


class BulkVisualRegistrationTests(unittest.TestCase):
    def _photo_fixture(self, root, colour="red", source_id="commons:1"):
        source = root / f"{colour}.png"
        Image.new("RGB", (320, 260), colour).save(source)
        candidate = SimpleNamespace(source_id=source_id, direct_url="", beat_key="origin",
            creator="Creator", license="CC BY", source="commons",
            source_page="https://example.test/item", required_identity=("Story X",))
        validation = SimpleNamespace(accepted=True, temp_path=source, verdict="DIRECT", sha256="")
        return candidate, validation

    def test_merge_preserves_bogle_entries(self):
        original = {"assets": {
            "bogle-vanguard-1959.jpg": {"stories": {"Jack Bogle": "DIRECT"}},
            "edison-stock-ticker.jpg": {"stories": {"Jack Bogle": "WEAK_GENERIC"}},
        }}
        result = merge_relevance_entry(copy.deepcopy(original), "bulk-story-x-origin-abc.jpg", "Story X", "DIRECT", "https://example.com/photo")
        self.assertEqual(result["assets"]["bogle-vanguard-1959.jpg"], original["assets"]["bogle-vanguard-1959.jpg"])
        self.assertEqual(result["assets"]["edison-stock-ticker.jpg"], original["assets"]["edison-stock-ticker.jpg"])

    def test_index_line_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "images.txt"
            self.assertTrue(append_index_line(path, "x.jpg", ["Story X"], "Commons / CC BY 4.0"))
            self.assertFalse(append_index_line(path, "x.jpg", ["Story X"], "Commons / CC BY 4.0"))
            self.assertEqual(path.read_text(encoding="utf-8").count("x.jpg"), 1)

    def test_logo_alias_merge_is_idempotent(self):
        index = {"apple.com": ["Apple"]}
        first = merge_logo_aliases(index, "apple.com", ["Apple", "Steve Jobs"])
        second = merge_logo_aliases(first, "apple.com", ["Steve Jobs"])
        self.assertEqual(second["apple.com"].count("Steve Jobs"), 1)

    def test_verified_logo_domain_is_added_once(self):
        text = "قصة Steve Jobs: الطرد من شركته ثم العودة | Steve Jobs\n"
        once = add_logo_domain_to_story_text(text, "قصة Steve Jobs: الطرد من شركته ثم العودة", "apple.com")
        twice = add_logo_domain_to_story_text(once, "قصة Steve Jobs: الطرد من شركته ثم العودة", "apple.com")
        self.assertEqual(twice.count("logo:apple.com"), 1)

    def test_conflicting_logo_domain_fails_closed(self):
        text = "قصة Tesla | Tesla, logo:tesla.com\n"
        with self.assertRaises(LogoIdentityConflict):
            add_logo_domain_to_story_text(text, "قصة Tesla", "apple.com")

    def test_content_sha_is_required_fallback_for_source_less_candidate(self):
        candidate = SimpleNamespace(source_id="", direct_url="", beat_key="origin")
        with self.assertRaises(RegistrationInvariantError):
            deterministic_photo_name("Story X", candidate)
        self.assertNotEqual(deterministic_photo_name("Story X", candidate, "aaa"),
                            deterministic_photo_name("Story X", candidate, "bbb"))

    def test_photo_registration_is_idempotent_and_rejects_differing_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); images = root / "images"
            index, ledger = images / "images.txt", images / "relevance.json"
            candidate, validation = self._photo_fixture(root)
            first = register_photo("Story X", candidate, validation, image_dir=images,
                index_path=index, ledger_path=ledger)
            state = (first.read_bytes(), index.read_bytes(), ledger.read_bytes())
            register_photo("Story X", candidate, validation, image_dir=images,
                index_path=index, ledger_path=ledger)
            self.assertEqual(state, (first.read_bytes(), index.read_bytes(), ledger.read_bytes()))
            _, different = self._photo_fixture(root, "blue")
            with self.assertRaises(RegistrationInvariantError):
                register_photo("Story X", candidate, different, image_dir=images,
                    index_path=index, ledger_path=ledger)
            self.assertEqual(state, (first.read_bytes(), index.read_bytes(), ledger.read_bytes()))

    def test_photo_late_write_failure_rolls_back_all_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); images = root / "images"
            index, ledger = images / "images.txt", images / "relevance.json"
            index.parent.mkdir(); index.write_text("seed\n", encoding="utf-8")
            ledger.write_text('{"assets": {}}\n', encoding="utf-8")
            before = (index.read_bytes(), ledger.read_bytes())
            candidate, validation = self._photo_fixture(root)
            original = registration._atomic_text
            calls = 0
            def fail_ledger(path, text):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected ledger failure")
                return original(path, text)
            with patch.object(registration, "_atomic_text", side_effect=fail_ledger):
                with self.assertRaises(OSError):
                    register_photo("Story X", candidate, validation, image_dir=images,
                        index_path=index, ledger_path=ledger)
            self.assertEqual(before, (index.read_bytes(), ledger.read_bytes()))
            self.assertEqual(list(images.glob("bulk-*")), [])

    def test_logo_late_story_write_failure_rolls_back_all_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = root / "logo.jpg"
            Image.new("RGB", (320, 260), "red").save(source)
            logos, index, stories = root / "logos", root / "index.json", root / "stories.txt"
            index.write_text('{"seed": ["Seed"]}\n', encoding="utf-8")
            stories.write_text("Story X | Story X\n", encoding="utf-8")
            before = (index.read_bytes(), stories.read_bytes())
            original = registration._atomic_text
            calls = 0
            def fail_story(path, text):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected story failure")
                return original(path, text)
            with patch.object(registration, "_atomic_text", side_effect=fail_story):
                with self.assertRaises(OSError):
                    register_logo(source, "Story X", "example.com", logos_dir=logos,
                        index_path=index, stories_path=stories)
            self.assertEqual(before, (index.read_bytes(), stories.read_bytes()))
            self.assertFalse((logos / "example.com-current.png").exists())
