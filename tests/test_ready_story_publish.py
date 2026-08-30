import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

import ready_story_publish as rsp


class ReadyStoryPublishTests(unittest.TestCase):
    def test_collect_ready_stories_keeps_only_strict_pass(self):
        stories = ["ready-a", "needs-photo", "ready-b"]
        coverage = {
            "ready-a": (list(range(4)), ["logo"], "PASS"),
            "needs-photo": (list(range(3)), ["logo"], "NEEDS 1 MORE PHOTO"),
            "ready-b": (list(range(5)), ["logo"], "PASS"),
        }

        ready = rsp.collect_ready_stories(
            stories,
            coverage_fn=lambda story: coverage[story],
        )

        self.assertEqual(ready, ["ready-a", "ready-b"])

    def test_publish_frames_posts_each_snap_separately(self):
        calls = []

        def post_fn(caption, media_urls, card_path):
            calls.append((caption, list(media_urls), card_path))
            return {"status": "success"}

        published = rsp.publish_frames_sequentially(
            "caption",
            ["1.png", "2.png", "3.png"],
            post_fn=post_fn,
            post_ok_fn=lambda response: response.get("status") == "success",
        )

        self.assertEqual(published, 3)
        self.assertEqual([call[2] for call in calls], ["1.png", "2.png", "3.png"])
        self.assertTrue(all(call[1] == [] for call in calls))

    def test_publish_frames_stops_on_first_failure(self):
        calls = []

        def post_fn(caption, media_urls, card_path):
            calls.append(card_path)
            if card_path == "2.png":
                return {"status": "error"}
            return {"status": "success"}

        with self.assertRaises(SystemExit):
            rsp.publish_frames_sequentially(
                "caption",
                ["1.png", "2.png", "3.png"],
                post_fn=post_fn,
                post_ok_fn=lambda response: response.get("status") == "success",
            )

        self.assertEqual(calls, ["1.png", "2.png"])

    def test_persist_visual_revision_commits_only_existing_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            revision_dir = root / "rev"
            revision_dir.mkdir()
            calls = []
            path = rsp.persist_visual_revision(
                "story",
                revision_fn=lambda _story: "abc123",
                state_dir_fn=lambda _story, _rev: revision_dir,
                commit_fn=lambda target, message: calls.append((Path(target), message)),
            )
            self.assertEqual(revision_dir, path)
            self.assertEqual(1, len(calls))
            self.assertIn("abc123", calls[0][1])

    def test_persist_visual_revision_does_not_commit_missing_state(self):
        with tempfile.TemporaryDirectory() as td:
            calls = []
            path = rsp.persist_visual_revision(
                "story",
                revision_fn=lambda _story: "abc123",
                state_dir_fn=lambda _story, _rev: Path(td) / "missing",
                commit_fn=lambda target, message: calls.append((target, message)),
            )
            self.assertFalse(path.exists())
            self.assertEqual([], calls)

    def test_ensure_subject_logo_visible_adds_contrast_backplate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            frame = root / "frame.png"
            logo = root / "logo.png"

            Image.new("RGB", (1080, 1920), (238, 232, 227)).save(frame)
            mark = Image.new("RGBA", (320, 150), (0, 0, 0, 0))
            draw = ImageDraw.Draw(mark)
            draw.rectangle((20, 35, 300, 115), fill=(226, 196, 112, 255))
            mark.save(logo)

            rsp.ensure_subject_logo_visible(
                "Story A",
                [frame],
                coverage_fn=lambda story: ([], [logo], "PASS"),
            )

            rendered = Image.open(frame).convert("RGB")
            panel_luma = sum(rendered.getpixel((710, 465))) / 3
            mark_luma = sum(rendered.getpixel((830, 535))) / 3
            self.assertLess(panel_luma, 120)
            self.assertGreater(mark_luma, 150)
            self.assertGreater(mark_luma - panel_luma, 60)

    def test_saudi_coffee_logo_gets_readable_contrast(self):
        logo = Path("images/logos/saudicoffee.com-current.png")
        self.assertTrue(logo.exists(), "Saudi Coffee logo asset must exist")
        with tempfile.TemporaryDirectory() as td:
            frame = Path(td) / "frame.png"
            Image.new("RGB", (1080, 1920), (238, 232, 227)).save(frame)

            rsp.ensure_subject_logo_visible(
                "قصة القهوة السعودية",
                [frame],
                coverage_fn=lambda story: ([], [logo], "PASS"),
            )

            rendered = Image.open(frame).convert("RGB")
            panel = rendered.crop((700, 455, 960, 615))
            luminance = [sum(px) / 3 for px in panel.getdata()]
            self.assertLess(min(luminance), 120)
            self.assertGreater(max(luminance), 150)
            self.assertGreater(max(luminance) - min(luminance), 60)


if __name__ == "__main__":
    unittest.main()