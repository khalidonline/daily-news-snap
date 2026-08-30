import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

import ready_story_publish as rsp
import story_bot as sb


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

    def test_review_deck_is_never_publishable(self):
        with self.assertRaises(SystemExit):
            rsp.require_ready_for_publication("REVIEW", "قصة تأسيس مؤسسة النقد ساما")

    def test_ready_deck_is_publishable(self):
        rsp.require_ready_for_publication("READY", "story")

    def test_typographic_frames_still_count_as_missing_visuals(self):
        frames = [
            {"text": "1952"},
            {"text": "1953"},
            {"text": "1954"},
            {"text": "1955"},
            {"text": "photo"},
            {"text": "photo"},
        ]
        photos = [None, None, None, None, "5.jpg", "6.jpg"]
        self.assertEqual(sb._missing_visual_indices(frames, photos), [1, 2, 3, 4])

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

    def test_persist_visual_revision_discovers_child_revision_when_parent_hash_differs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "story-id"
            child_revision = root / "child-revision"
            child_revision.mkdir(parents=True)
            (child_revision / "state.json").write_text("{}\n", encoding="utf-8")
            calls = []

            path = rsp.persist_visual_revision(
                "story",
                revision_fn=lambda _story: "parent-revision",
                state_dir_fn=lambda _story, revision: root / revision,
                commit_fn=lambda target, message: calls.append((Path(target), message)),
            )

            self.assertEqual(child_revision, path)
            self.assertEqual([(child_revision, "story visual state: child-revisi")], calls)

    def test_child_render_suppresses_intermediate_telegram(self):
        fake_result = mock.Mock(returncode=1, stdout="", stderr="blocked")
        with mock.patch.object(rsp, "persist_editorial_state"):
            with mock.patch.object(rsp.subprocess, "run", return_value=fake_result) as run:
                with self.assertRaises(SystemExit):
                    rsp.build_story_without_posting("story")
        self.assertEqual("1", run.call_args.kwargs["env"]["STORY_SUPPRESS_TELEGRAM"])
        self.assertEqual("0", run.call_args.kwargs["env"]["POST_TO_SNAPCHAT"])

    def test_failed_child_persists_editorial_state_before_exit(self):
        fake_result = mock.Mock(returncode=1, stdout="", stderr="blocked")
        with mock.patch.object(rsp, "persist_editorial_state") as persist:
            with mock.patch.object(rsp.subprocess, "run", return_value=fake_result):
                with self.assertRaises(SystemExit):
                    rsp.build_story_without_posting("story")
        persist.assert_called_once_with()

    def test_persist_editorial_state_commits_guard_ledger_and_briefs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cost = root / "cost"
            briefs = root / "briefs"
            (cost / "model_call_guard").mkdir(parents=True)
            (cost / "model_usage.jsonl").write_text("{}\n", encoding="utf-8")
            briefs.mkdir()
            calls = []
            with mock.patch.dict(
                "os.environ",
                {"STORY_COST_STATE_ROOT": str(cost), "STORY_BRIEF_ROOT": str(briefs)},
            ):
                rsp.persist_editorial_state(
                    commit_fn=lambda target, message: calls.append((Path(target), message))
                )
            self.assertEqual(
                {cost / "model_usage.jsonl", cost / "model_call_guard", briefs},
                {target for target, _message in calls},
            )

    def test_final_ready_candidate_notifies_once_then_dedupes(self):
        calls = []
        claims = iter([Path("claim"), None])
        kwargs = dict(
            story="story",
            frames=["1.png", "2.png"],
            status="READY",
            revision="rev",
            digest="hash",
            claim_fn=lambda *args: next(claims),
            notify_fn=lambda caption, frames, as_documents=True: calls.append((caption, tuple(frames))),
            complete_fn=lambda *args: None,
            release_fn=lambda *args: None,
            persist_fn=lambda: None,
        )
        self.assertTrue(rsp.notify_final_candidate(**kwargs))
        self.assertFalse(rsp.notify_final_candidate(**kwargs))
        self.assertEqual(1, len(calls))
        self.assertIn("READY", calls[0][0])

    def test_blocked_candidate_never_notifies(self):
        called = []
        sent = rsp.notify_final_candidate(
            "story", ["1.png"], "BLOCKED", "rev", "hash",
            claim_fn=lambda *args: called.append(args),
            notify_fn=lambda *args, **kwargs: called.append("notify"),
            complete_fn=lambda *args: None,
            release_fn=lambda *args: None,
            persist_fn=lambda: None,
        )
        self.assertFalse(sent)
        self.assertEqual([], called)

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
