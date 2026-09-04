import unittest

import news_bot


class BreakingPinnedArticleTests(unittest.TestCase):
    def test_confirmed_article_url_is_attached_to_pinned_story(self):
        stories = [{"headline": "ROX starts production"}]
        result = news_bot.attach_pinned_event_url(
            stories, "https://www.wam.ae/example"
        )

        self.assertEqual("https://www.wam.ae/example", result[0]["link"])

    def test_non_http_url_is_ignored(self):
        stories = [{"headline": "ROX starts production"}]
        result = news_bot.attach_pinned_event_url(stories, "file:///tmp/image")

        self.assertNotIn("link", result[0])


if __name__ == "__main__":
    unittest.main()
