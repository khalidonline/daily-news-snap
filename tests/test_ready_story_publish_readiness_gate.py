import unittest

import ready_story_publish as rsp


class ReadyStoryPublicationGateTests(unittest.TestCase):
    def test_visual_pass_without_publication_evidence_is_not_ready(self):
        stories = ["visual-only", "publication-ready"]
        coverage = {
            "visual-only": (list(range(4)), ["logo"], "PASS"),
            "publication-ready": (list(range(4)), ["logo"], "PASS"),
        }

        ready = rsp.collect_ready_stories(
            stories,
            coverage_fn=lambda story: coverage[story],
            publication_ready_fn=lambda story: story == "publication-ready",
        )

        self.assertEqual(["publication-ready"], ready)

    def test_non_visual_pass_never_becomes_ready_even_with_publication_evidence(self):
        ready = rsp.collect_ready_stories(
            ["needs-photo"],
            coverage_fn=lambda _story: (list(range(3)), ["logo"], "NEEDS 1 MORE PHOTO"),
            publication_ready_fn=lambda _story: True,
        )

        self.assertEqual([], ready)


if __name__ == "__main__":
    unittest.main()
