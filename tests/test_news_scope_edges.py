import unittest

from news_editorial import hard_scope_eligible


class NewsScopeEdgeTests(unittest.TestCase):
    def test_foreign_politics_with_saudi_name_but_no_concrete_impact_is_rejected(self):
        item = {
            "lane": "saudi_core",
            "source": "example",
            "title": "ترامب يتحدث عن السعودية في لقاء سياسي جديد",
            "summary": "تصريحات سياسية عامة دون قرار اقتصادي أو أثر مباشر على الناس.",
        }
        self.assertFalse(hard_scope_eligible(item))

    def test_foreign_policy_with_direct_saudi_economic_consequence_can_qualify(self):
        item = {
            "lane": "business_tech",
            "source": "example",
            "title": "ترامب يعلن قراراً يخفض رسوماً على صادرات سعودية",
            "summary": "التغيير يطبق مباشرة على صادرات المملكة ويغير تكلفة التجارة.",
        }
        self.assertTrue(hard_scope_eligible(item))

    def test_routine_weather_forecast_is_rejected(self):
        item = {
            "lane": "saudi_core",
            "source": "example",
            "title": "أمطار رعدية متوقعة على 5 مناطق السبت",
            "summary": "توقعات طقس اعتيادية لعدة مناطق.",
        }
        self.assertFalse(hard_scope_eligible(item))

    def test_weather_causing_major_airport_disruption_can_qualify(self):
        item = {
            "lane": "travel_lifestyle",
            "source": "example",
            "title": "أمطار غزيرة تغلق مطاراً سعودياً وتلغي عشرات الرحلات",
            "summary": "إلغاء واسع للرحلات يؤثر في المسافرين حتى إشعار آخر.",
        }
        self.assertTrue(hard_scope_eligible(item))

    def test_accident_death_lawsuit_story_is_rejected(self):
        item = {
            "lane": "travel_lifestyle",
            "source": "example",
            "title": "زوجة راكب توفي بعد اضطراب جوي تقاضي شركة طيران",
            "summary": "دعوى مرتبطة بوفاة راكب بعد اضطراب جوي خلال رحلة دولية.",
        }
        self.assertFalse(hard_scope_eligible(item))

    def test_national_transport_safety_regulation_can_qualify(self):
        item = {
            "lane": "travel_lifestyle",
            "source": "example",
            "title": "هيئة الطيران تصدر قواعد سلامة جديدة تلزم شركات الطيران",
            "summary": "قرار تنظيمي جديد يطبق على جميع شركات الطيران والمسافرين في السعودية.",
        }
        self.assertTrue(hard_scope_eligible(item))


if __name__ == "__main__":
    unittest.main()
