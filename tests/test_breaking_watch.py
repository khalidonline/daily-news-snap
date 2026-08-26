import importlib
import sys
import types
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch


class _Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


def _load_module():
    fake = types.ModuleType("news_bot")
    fake.ANTHROPIC_API_KEY = "test"
    fake.DRY_RUN = True
    fake.commit_and_push = lambda *args, **kwargs: None
    fake.ksa_stamp = lambda: "test"
    fake.notify = lambda *args, **kwargs: None
    sys.modules["news_bot"] = fake
    sys.modules.pop("breaking_watch", None)
    return importlib.import_module("breaking_watch")


class BreakingFeedTests(unittest.TestCase):
    def test_normal_rss_title_reaches_fresh_items(self):
        bw = _load_module()
        bw.WATCH_FEEDS = ["https://example.test/rss"]
        rss = (
            b"<rss><channel><item>"
            b"<title>Saudi breaking headline</title>"
            b"<pubDate>Wed, 26 Aug 2099 12:00:00 GMT</pubDate>"
            b"</item></channel></rss>"
        )
        with patch.object(
            bw.urllib.request, "urlopen", return_value=_Response(rss)
        ):
            fresh, feeds_ok = bw.feed_fresh_items()
        self.assertTrue(feeds_ok)
        self.assertEqual(["Saudi breaking headline"], fresh)

    def test_feed_scan_reports_item_and_fresh_counts(self):
        bw = _load_module()
        bw.WATCH_FEEDS = ["https://example.test/rss"]
        rss = (
            b"<rss><channel><item>"
            b"<title>Saudi breaking headline</title>"
            b"<pubDate>Wed, 26 Aug 2099 12:00:00 GMT</pubDate>"
            b"</item></channel></rss>"
        )
        output = StringIO()
        with patch.object(
            bw.urllib.request, "urlopen", return_value=_Response(rss)
        ), redirect_stdout(output):
            bw.feed_fresh_items()
        self.assertIn("1 item(s), 1 fresh", output.getvalue())

    def test_default_feed_window_covers_scheduler_delay(self):
        bw = _load_module()
        self.assertEqual(120, bw.WATCH_FEED_WINDOW_MIN)


if __name__ == "__main__":
    unittest.main()
