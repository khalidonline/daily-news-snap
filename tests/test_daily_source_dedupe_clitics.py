import unittest

import daily_news_runner


class DailySourceDedupeCliticTests(unittest.TestCase):
    def test_arabic_attached_clitics_normalize_to_same_story_token(self):
        base = daily_news_runner._dedupe_tokens("النصر")
        self.assertEqual(base, daily_news_runner._dedupe_tokens("للنصر"))
        self.assertEqual(base, daily_news_runner._dedupe_tokens("والنصر"))
        self.assertEqual(base, daily_news_runner._dedupe_tokens("بالنصر"))


if __name__ == "__main__":
    unittest.main()
