import unittest

import story_delivery_recovery as recovery


class StoryDeliveryRecoveryTests(unittest.TestCase):
    def test_retries_until_the_story_is_delivered(self):
        outcomes = iter([1, 1, 0])
        attempts = []

        result = recovery.run_until_delivered(
            lambda: attempts.append(len(attempts) + 1) or next(outcomes),
            max_attempts=3,
        )

        self.assertEqual(result, 0)
        self.assertEqual(attempts, [1, 2, 3])

    def test_stops_after_the_bounded_attempt_budget(self):
        attempts = []

        result = recovery.run_until_delivered(
            lambda: attempts.append(len(attempts) + 1) or 1,
            max_attempts=3,
        )

        self.assertEqual(result, 1)
        self.assertEqual(attempts, [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
