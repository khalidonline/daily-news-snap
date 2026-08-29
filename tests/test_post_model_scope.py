import unittest

import daily_news_runner


class PostModelScopeTests(unittest.TestCase):
    def test_rejects_transfer_created_by_model_rewrite(self):
        shortlist = [{
            "lane": "sports",
            "source": "اليوم",
            "title": "الهلال يدرس خيارات الهجوم للموسم الجديد",
            "summary": "النادي يدرس عدة أسماء في سوق الانتقالات.",
        }]
        result = {"stories": [{
            "item": 1,
            "headline": "واتكينز في طريقه للانضمام رسمياً للهلال",
            "summary": "الصفقة تتجه للحسم لكن لا يوجد إعلان من النادي.",
            "takeaway": "انتقال كبير محتمل للهلال.",
        }]}

        filtered = daily_news_runner.validate_ranked_result(result, shortlist)
        self.assertEqual(filtered["stories"], [])

    def test_rejects_personal_health_advice_created_by_model_rewrite(self):
        shortlist = [{
            "lane": "saudi_core",
            "source": "اليوم",
            "title": "وزارة الصحة تجيب عن تساؤل متداول",
            "summary": "توضيح جديد نشرته الوزارة اليوم.",
        }]
        result = {"stories": [{
            "item": 1,
            "headline": "وزارة الصحة تنفي أن الشاي بدون سكر يضر الكبد",
            "summary": "توضيح صحي عن تأثير شرب الشاي على الكبد.",
            "takeaway": "معلومة صحية للاستخدام اليومي.",
        }]}

        filtered = daily_news_runner.validate_ranked_result(result, shortlist)
        self.assertEqual(filtered["stories"], [])

    def test_keeps_valid_model_rewrite_when_source_and_card_are_in_scope(self):
        shortlist = [{
            "lane": "business_tech",
            "source": "The Verge",
            "title": "Google changes how search results are displayed",
            "summary": "A major consumer search change affects users.",
        }]
        story = {
            "item": 1,
            "headline": "Google تدفع نتائج البحث التقليدية أسفل ملخصات AI",
            "summary": "تغيير واسع في تجربة البحث لدى Google.",
            "takeaway": "المستخدم يرى إجابات AI قبل الروابط التقليدية.",
        }

        filtered = daily_news_runner.validate_ranked_result({"stories": [story]}, shortlist)
        self.assertEqual(filtered["stories"], [story])


if __name__ == "__main__":
    unittest.main()
