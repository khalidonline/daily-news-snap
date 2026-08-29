import unittest

from news_editorial import hard_scope_eligible


class LiveHealthScopeTests(unittest.TestCase):
    def test_ministry_denial_about_tea_and_liver_is_personal_health_content(self):
        item = {
            "lane": "saudi_core",
            "source": "اليوم",
            "title": "الصحة: لا دليل على أن الشاي بلا سكر يضر الكبد",
            "summary": "وزارة الصحة توضح أن شرب الشاي بدون سكر لا يثبت أنه يسبب ضرراً للكبد.",
        }
        self.assertFalse(hard_scope_eligible(item))

    def test_actual_ministry_policy_decision_stays_eligible(self):
        item = {
            "lane": "saudi_core",
            "source": "اليوم",
            "title": "وزارة الصحة توسع التغطية التأمينية للقاحات السفر",
            "summary": "قرار وطني جديد يطبق على وثائق التأمين في السعودية.",
        }
        self.assertTrue(hard_scope_eligible(item))


if __name__ == "__main__":
    unittest.main()
