import unittest

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


if __name__ == "__main__":
    unittest.main()
