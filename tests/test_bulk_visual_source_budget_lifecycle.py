import unittest

from tools.bulk_visual_sources import (
    SourceDiscoveryBudget,
    SourceDiscoveryBudgetExceeded,
    StoryBeat,
    discover_openverse,
)


class SourceDiscoveryBudgetLifecycleTests(unittest.TestCase):
    def test_idle_reviewer_time_does_not_consume_source_budget(self):
        now = [0.0]
        budget = SourceDiscoveryBudget("openverse", seconds=18, max_requests=4,
                                       clock=lambda: now[0])
        beat = StoryBeat("person", ("Target Person photograph",), ("Target Person",),
                         "person")

        def response(_url):
            now[0] += 3.0
            return {"page_count": 1, "results": []}

        self.assertEqual(discover_openverse(beat, json_get=response, budget=budget), [])
        self.assertEqual(budget.elapsed, 3.0)

        # Simulate image validation/model review and other source work between
        # two beats. None of this is Openverse discovery time.
        now[0] += 30.0

        self.assertEqual(discover_openverse(beat, json_get=response, budget=budget), [])
        self.assertEqual(budget.elapsed, 6.0)
        self.assertFalse(budget.disabled)

    def test_separate_discovery_calls_accumulate_to_the_same_cap(self):
        now = [0.0]
        budget = SourceDiscoveryBudget("openverse", seconds=18, max_requests=4,
                                       clock=lambda: now[0])
        beat = StoryBeat("person", ("Target Person photograph",), ("Target Person",),
                         "person")

        def response(_url):
            now[0] += 9.0
            return {"page_count": 1, "results": []}

        self.assertEqual(discover_openverse(beat, json_get=response, budget=budget), [])
        self.assertEqual(discover_openverse(beat, json_get=response, budget=budget), [])
        self.assertEqual(budget.elapsed, 18.0)
        self.assertTrue(budget.exhausted())
        with self.assertRaises(SourceDiscoveryBudgetExceeded):
            discover_openverse(beat, json_get=response, budget=budget)

    def test_each_request_timeout_is_capped_by_remaining_active_budget(self):
        now = [0.0]
        budget = SourceDiscoveryBudget("loc", seconds=10, max_requests=4,
                                       clock=lambda: now[0])

        with budget.active():
            self.assertEqual(budget.begin_request(), 9.0)
            now[0] += 7.0
            self.assertEqual(budget.begin_request(), 3.0)

        self.assertEqual(budget.elapsed, 7.0)


if __name__ == "__main__":
    unittest.main()
