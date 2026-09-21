import unittest
from unittest.mock import patch
from publishing_v2.autopilot import eligibility
from publishing_v2.autopilot.sources import Sources
import test_v2_autopilot as fixtures


class EligibilityTests(unittest.TestCase):
    def test_observed_medical_and_obituary_triggers_are_excluded(self):
        for title in ['تأثير تناول الجوافة على مرضى الكوليسترول المرتفع',
                      'وفاة الشيخ أحمد بن راشد آل مكتوم… ودبي تعلن الحداد 10 أيام',
                      "Presley Gerber, Cindy Crawford's son, dies aged 27",
                      'Foods to lower cholesterol', 'فوائد القرفة لمرضى السكري']:
            with self.subTest(title=title):
                self.assertIsNotNone(eligibility.routine_trigger_rejection({'title':title}))

    def test_everyday_subjects_and_incidental_history_remain_available(self):
        for title in ['انطلاق مهرجان الجوافة في جازان', 'افتتاح مستشفى جديد في جدة',
                      'شركة تطلق تطبيق حجز مواعيد للمرضى', 'Death Stranding arrives on a new console',
                      'الفيلم الجديد يروي قصة الموت والحياة', 'تاريخ شركة غذاء سعودية',
                      'رحيل لاعب الهلال إلى فريق جديد']:
            with self.subTest(title=title):
                self.assertIsNone(eligibility.routine_trigger_rejection({
                    'title':title, 'summary':'بعد وفاة المؤسس قبل مئة عام استمرت الشركة'}))

    def test_hospital_services_are_not_medical_advice(self):
        for title in ['New hospital app helps patients manage appointments',
                      'Hospital opens food court for patients and visitors',
                      'Saudi hospital expands parking benefits for patients',
                      'المجلس يتناول تطوير خدمات النقل للمرضى',
                      'افتتاح مركز علاج السكري في جدة']:
            with self.subTest(title=title):
                self.assertIsNone(eligibility.routine_trigger_rejection({'title':title}))

    def test_filtered_feed_items_do_not_use_eligible_topic_quota(self):
        from xml.sax.saxutils import escape
        titles = ['وفاة شخصية معروفة'] * 12 + ['افتتاح مهرجان جدة'] * 12
        items = ''.join('<item><title>'+escape(title)+'</title><link>https://www.bbc.com/news/'+str(i)+
            '</link><description>مهرجان جديد في جدة</description><pubDate>Thu, 17 Sep 2026 08:00:00 GMT</pubDate></item>'
            for i,title in enumerate(titles))
        source = Sources()
        with patch('publishing_v2.autopilot.sources.FEEDS', ('https://feeds.bbci.co.uk/news/rss.xml',)), \
             patch('publishing_v2.autopilot.sources.fetch', return_value=('<rss><channel>'+items+'</channel></rss>').encode()):
            rows = source.discover('daily', fixtures.NOW)
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(row['title']=='افتتاح مهرجان جدة' for row in rows))


class EligibilityPipelineTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    pipeline = fixtures.PipelineTests.pipeline
    render = fixtures.PipelineTests.render
    publish = fixtures.PipelineTests.publish

    def test_all_ineligible_stops_before_any_paid_role(self):
        pipeline = self.pipeline()
        pipeline.sources.discover = lambda lane, now: [{'id':'medical',
            'title':'تأثير تناول الجوافة على مرضى الكوليسترول المرتفع'}]
        result = pipeline.run('daily','shadow')
        self.assertEqual(self.agent.calls, [])
        self.assertEqual(result['status'], 'held')
        self.assertEqual(result['eligibility_rejections'][0]['reason'],'medical_advice_trigger')

    def test_ineligible_cannot_consume_editor_shortlist(self):
        pipeline = self.pipeline()
        original_discover = pipeline.sources.discover
        pipeline.sources.discover = lambda lane, now: [{'id':'obituary','title':'وفاة شخصية معروفة'}] + original_discover(lane,now)
        original_run, seen = self.agent.run, []
        def run(role, data, images=()):
            if role=='editor': seen.extend(row['id'] for row in data['candidates'])
            return original_run(role,data,images)
        self.agent.run = run
        result = pipeline.run('daily','shadow')
        self.assertEqual(seen,['a','b'])
        self.assertEqual(result['status'],'shadow_passed')
