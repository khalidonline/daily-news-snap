import sys
import types
import unittest

_fake_news_bot = types.ModuleType("news_bot")
_fake_news_bot.ANTHROPIC_API_KEY = "test-key"
_fake_news_bot.DRY_RUN = True
_fake_news_bot.commit_and_push = lambda *args, **kwargs: None
_fake_news_bot.ksa_stamp = lambda: "test-stamp"
_fake_news_bot.notify = lambda *args, **kwargs: None
sys.modules.setdefault("news_bot", _fake_news_bot)

import breaking_watch
import breaking_watch_entry


class TrustedVerificationTests(unittest.TestCase):
    def setUp(self):
        self.original_prompt = breaking_watch.WATCH_PROMPT

    def tearDown(self):
        breaking_watch.WATCH_PROMPT = self.original_prompt

    def test_installed_rule_requires_reuters_ap_or_official_check_before_rejection(self):
        breaking_watch_entry._install_trusted_verification_rule()
        prompt = breaking_watch.WATCH_PROMPT
        self.assertIn("Reuters", prompt)
        self.assertIn("AP", prompt)
        self.assertIn("مصدر رسمي", prompt)
        self.assertIn("قبل الرفض", prompt)
        self.assertIn("عسكري", prompt)
        self.assertIn("ملاحة", prompt)

    def test_rule_is_idempotent(self):
        breaking_watch_entry._install_trusted_verification_rule()
        once = breaking_watch.WATCH_PROMPT
        breaking_watch_entry._install_trusted_verification_rule()
        self.assertEqual(breaking_watch.WATCH_PROMPT, once)

    def test_rule_does_not_add_another_paid_search(self):
        breaking_watch_entry._install_trusted_verification_rule()
        self.assertEqual(
            breaking_watch._classifier_search_budget(["Saudi Gulf security candidate"]),
            1,
        )


if __name__ == "__main__":
    unittest.main()
