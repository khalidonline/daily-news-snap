import unittest
from unittest.mock import patch

import auto_publish_gate as gate


def state(candidate_id, subject):
    return {
        "package": {
            "candidate": {
                "id": candidate_id,
                "resolved_subjects": [{"name": subject}],
                "editorial": {"research_query": subject},
            }
        }
    }


class AutoPublishGateTests(unittest.TestCase):
    def test_duplicate_local_is_blocked_while_daily_can_publish(self):
        daily = {"action":"publish","reason":None,"state":state("same","Saudi Aramco")}
        local = {"action":"publish","reason":None,"state":state("same","Saudi Aramco")}
        with patch.object(gate, "_load_lane", side_effect=[daily, local]):
            result = gate.decide({}, "engine", None)
        self.assertEqual(result["daily"]["action"], "publish")
        self.assertEqual(result["local"], {
            "action":"blocked", "reason":"duplicate_with_daily"
        })

    def test_same_subject_is_blocked_even_with_different_candidate_id(self):
        daily = {"action":"publish","reason":None,"state":state("d1","Saudi Aramco")}
        local = {"action":"publish","reason":None,"state":state("l1","Saudi Aramco")}
        with patch.object(gate, "_load_lane", side_effect=[daily, local]):
            result = gate.decide({}, "engine", None)
        self.assertEqual(result["local"]["reason"], "duplicate_with_daily")

    def test_distinct_reviewed_lanes_are_publishable(self):
        daily = {"action":"publish","reason":None,"state":state("d1","Saudi Aramco")}
        local = {"action":"publish","reason":None,"state":state("l1","Jeddah")}
        with patch.object(gate, "_load_lane", side_effect=[daily, local]):
            result = gate.decide({}, "engine", None)
        self.assertEqual(result["daily"]["action"], "publish")
        self.assertEqual(result["local"]["action"], "publish")

    def test_local_cannot_publish_without_daily_contract(self):
        daily = {"action":"blocked","reason":"shadow_not_passed","state":{}}
        local = {"action":"publish","reason":None,"state":state("l1","Jeddah")}
        with patch.object(gate, "_load_lane", side_effect=[daily, local]):
            result = gate.decide({}, "engine", None)
        self.assertEqual(result["daily"]["action"], "blocked")
        self.assertEqual(result["local"], {
            "action":"blocked", "reason":"daily_not_publishable"
        })


if __name__ == "__main__":
    unittest.main()
