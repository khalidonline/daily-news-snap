import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import daily_news_runner
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

    def test_personal_health_advice_is_rejected_even_when_ministry_is_quoted(self):
        item = {
            "lane": "saudi_core",
            "source": "example",
            "title": "هل الشاي بدون سكر يضر الكبد؟ توضيح من وزارة الصحة",
            "summary": "وزارة الصحة توضح أثر شرب الشاي على صحة الكبد.",
        }
        self.assertFalse(hard_scope_eligible(item))

    def test_declarative_personal_health_explainer_is_rejected(self):
        item = {
            "lane": "saudi_core",
            "source": "اليوم",
            "title": "الصحة توضح حقيقة تأثير الشاي بدون سكر على الكبد",
            "summary": "توضيح صحي عن تأثير شرب الشاي دون سكر على الكبد.",
        }
        self.assertFalse(hard_scope_eligible(item))

    def test_ministry_health_policy_change_remains_eligible(self):
        item = {
            "lane": "saudi_core",
            "source": "example",
            "title": "وزارة الصحة توسع التغطية التأمينية للقاحات السفر",
            "summary": "قرار وطني جديد يطبق على وثائق التأمين في السعودية.",
        }
        self.assertTrue(hard_scope_eligible(item))

    def test_unconfirmed_transfer_report_is_rejected(self):
        item = {
            "lane": "sports",
            "source": "اليوم",
            "title": "تقارير: واتكينز يقترب من الانتقال رسمياً للهلال",
            "summary": "تقارير صحفية تتحدث عن قرب انتقال اللاعب إلى الهلال دون إعلان من النادي.",
        }
        self.assertFalse(hard_scope_eligible(item))

    def test_prospective_transfer_wording_is_rejected_without_announcement(self):
        item = {
            "lane": "sports",
            "source": "اليوم",
            "title": "الهلال يقترب من ضم أولي واتكينز رسمياً",
            "summary": "الصفقة تقترب من الحسم لكن لا يوجد إعلان رسمي من النادي حتى الآن.",
        }
        self.assertFalse(hard_scope_eligible(item))

    def test_in_route_transfer_wording_is_rejected_without_announcement(self):
        item = {
            "lane": "sports",
            "source": "اليوم",
            "title": "واتكينز في طريقه للانضمام رسمياً للهلال",
            "summary": "اللاعب في طريقه للانضمام للنادي، ولم يعلن الهلال التعاقد حتى الآن.",
        }
        self.assertFalse(hard_scope_eligible(item))

    def test_confirmed_major_transfer_remains_eligible(self):
        item = {
            "lane": "sports",
            "source": "example",
            "title": "الهلال يعلن رسمياً التعاقد مع واتكينز",
            "summary": "النادي أعلن الصفقة رسمياً عبر حساباته الرسمية.",
        }
        self.assertTrue(hard_scope_eligible(item))


class FinalImageQualityTests(unittest.TestCase):
    def test_article_neutral_beats_unrelated_local_neutral_as_last_resort(self):
        def write(path, label):
            Path(path).write_bytes(label.encode("utf-8"))
            return str(path)

        def local(queries_ar, queries_en, out_path, respect_cooldown=True, exclude=()):
            return write(out_path, "local"), "Local credit"

        def article(url, out_path):
            return write(out_path, "article"), "alyaum.com"

        def no_pair(*args, **kwargs):
            return None, None

        def no_stock(*args, **kwargs):
            return None

        def judge(path, context):
            label = Path(path).read_bytes().decode("utf-8")
            return "neutral" if label in {"local", "article"} else "no"

        fake = SimpleNamespace(
            PEXELS_API_KEY="",
            DOMAIN_CREDITS={"alyaum.com": "اليوم"},
            photo_shows=judge,
            fetch_local_photo=local,
            fetch_article_photo=article,
            fetch_spa_photo=no_pair,
            fetch_commons_photo=no_pair,
            fetch_loc_photo=no_pair,
            fetch_openverse_photo=no_pair,
            fetch_photo=no_stock,
        )
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "خبر رياضي سعودي مهم",
                "summary": "قصة رياضية واسعة الاهتمام.",
                "takeaway": "تهم جمهور الرياضة في السعودية.",
                "link": "https://www.alyaum.com/story",
                "scope": "saudi",
                "image_queries": ["saudi football"],
                "image_queries_ar": ["كرة القدم السعودية"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["كرة القدم السعودية"], ["saudi football"], hero)
            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "اليوم")
            self.assertEqual(hero.read_bytes(), b"article")


if __name__ == "__main__":
    unittest.main()
