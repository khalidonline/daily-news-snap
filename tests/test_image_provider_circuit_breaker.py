import unittest
from unittest.mock import patch

import news_bot


class ImageProviderCircuitBreakerTests(unittest.TestCase):
    def test_openverse_timeout_disables_later_queries_in_same_run(self):
        news_bot._openverse_unavailable = False
        with patch.object(
            news_bot.urllib.request,
            "urlopen",
            side_effect=TimeoutError("timed out"),
        ) as urlopen:
            self.assertEqual(news_bot._openverse_search("first"), [])
            self.assertEqual(news_bot._openverse_search("second"), [])

        self.assertEqual(urlopen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
