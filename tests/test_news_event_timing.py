import base64
import json
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import daily_news_runner as runner


class EventTimingTests(unittest.TestCase):
    def story(self):
        return {
            'headline': 'غداً.. الشوط رقم 4000', 'summary': 'موعد يستحق المتابعة',
            'takeaway': 'محطة في مسيرة المهرجان', 'link': 'https://example.com/race',
            'event_date': '2026-09-11', 'event_date_evidence': 'السباق غداً',
            'timing_source': {'title': 'السباق غداً', 'summary': '',
                              'published_at': '2026-09-10T19:39:00+03:00'},
        }

    def prepare(self, story, hour):
        self.assertTrue(hasattr(runner, 'prepare_news_delivery'),
                        'News needs a source-backed delivery date guard')
        return runner.prepare_news_delivery(story, now=datetime.fromisoformat(hour))

    def test_tomorrow_changes_to_today_at_saudi_midnight(self):
        story = self.story()
        before = self.prepare(story, '2026-09-10T20:59:00+00:00')
        after = self.prepare(story, '2026-09-10T21:00:00+00:00')
        self.assertIn('غداً', before['headline'])
        self.assertIn('اليوم', after['headline'])
        self.assertEqual(story['headline'], 'غداً.. الشوط رقم 4000')

    def test_unknown_event_date_cannot_use_publication_as_event_date(self):
        story = self.story()
        story['timing_source']['title'] = 'السباق يستعد لاستقبال المشاركين'
        with self.assertRaisesRegex(ValueError, 'timing evidence'):
            self.prepare(story, '2026-09-10T18:00:00+00:00')

    def test_future_date_must_match_source_evidence(self):
        story = self.story()
        story['event_date'] = '2026-09-12'
        with self.assertRaisesRegex(ValueError, 'timing evidence'):
            self.prepare(story, '2026-09-10T18:00:00+00:00')

    def test_expired_preview_does_not_become_an_unverified_result(self):
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.prepare(self.story(), '2026-09-12T10:00:00+00:00')

    def test_explicit_source_date_survives_recovery_without_publication_time(self):
        story = self.story()
        story['event_date_evidence'] = 'السباق في 2026-09-11'
        story['timing_source'] = {'title': story['event_date_evidence']}
        self.assertIn('اليوم', self.prepare(story, '2026-09-11T10:00:00+00:00')['headline'])

    def test_date_neutral_story_needs_no_event_timestamp(self):
        story = {'headline': 'نموذج جديد لتحليل القمر', 'summary': 'تفصيل مؤكد'}
        self.assertEqual(self.prepare(story, '2026-09-11T10:00:00+00:00'), story)

    def test_recovery_revalidates_without_calling_editorial_model(self):
        bot = SimpleNamespace(summarize=lambda *a: self.fail('paid generation'))
        encoded = base64.b64encode(json.dumps(self.story()).encode()).decode()
        prepare = runner.prepare_news_delivery
        with patch.dict('os.environ', {'NEWS_RECOVERY_STORY_B64': encoded}), patch.object(
            runner, 'prepare_news_delivery',
            side_effect=lambda story: prepare(story, now=datetime.fromisoformat('2026-09-12T10:00:00+00:00')),
        ):
            with self.assertRaisesRegex(ValueError, 'expired'):
                runner.make_summarizer(bot)([])

    def test_ibm_recovery_preserves_benchmark_qualifier_and_scope(self):
        story = {'headline': 'ذكاء IBM وناسا يرصد جليد القمر بدقة أعلى 23%',
                 'link': 'https://www.reuters.com/science/ibm-nasa-launch-ai-model-help-map-ice-craters-moon-2026-09-10/'}
        corrected = self.prepare(story, '2026-09-11T10:00:00+00:00')
        self.assertIn('تصل إلى 23%', corrected['headline'])
        self.assertIn('معالم القمر', corrected['headline'])
        self.assertNotIn('جليد', corrected['headline'])

    def test_source_metadata_is_bound_to_feed_not_invented_by_model(self):
        story = self.story()
        story.update(item=1, headline='غداً.. إطلاق هاتف Apple الجديد')
        source = {'title': 'Apple announces new phone',
                  'summary': 'A new camera feature for consumers',
                  'lane': 'business_tech'}
        result = runner.validate_ranked_result({'stories': [story]}, [source])
        self.assertEqual(result['stories'], [])

    def test_validated_source_evidence_is_retained_for_recovery(self):
        story = self.story()
        story.update(item=1, headline='غداً.. إطلاق هاتف Apple الجديد')
        source = {'title': 'Apple تطلق هاتفها غداً',
                  'summary': 'كاميرا جديدة للمستخدمين',
                  'published_at': '2026-09-10T15:00:00+03:00',
                  'lane': 'business_tech'}
        story['event_date_evidence'] = source['title']
        prepare = runner.prepare_news_delivery
        with patch.object(runner, 'prepare_news_delivery', side_effect=lambda s: prepare(
            s, now=datetime.fromisoformat('2026-09-10T18:00:00+00:00')
        )):
            selected = runner.validate_ranked_result({'stories': [story]}, [source])['stories'][0]
        self.assertEqual(selected['timing_source']['title'], source['title'])
        self.assertIn('اليوم', self.prepare(selected, '2026-09-10T21:00:00+00:00')['headline'])

    def test_shared_renderer_rechecks_after_photo_work_before_rendering(self):
        import tempfile
        from pathlib import Path
        import news_bot
        story = self.story()
        # Run the real main orchestration. Stub only I/O, generation and image
        # fetching so no provider or delivery request can be made by the test.
        rendered = []
        with tempfile.TemporaryDirectory() as tmp, patch.multiple(
            news_bot, OUT_DIR=Path(tmp), PINNED_EVENT='', DRY_RUN=True,
            REQUIRE_PHOTO=False, CANDIDATES=1,
        ), patch.object(news_bot, 'fetch_headlines', return_value=[{}] * 5), patch.object(
            news_bot, 'load_posted', return_value=[]
        ), patch.object(news_bot, 'summarize', return_value={'stories': [story]}), patch.object(
            news_bot, 'visual_story_candidates', return_value=[]
        ), patch.object(news_bot, 'recent_fallback', return_value=None), patch.object(
            news_bot, 'prepare_story_for_delivery',
            side_effect=lambda s: self.prepare(s, '2026-09-10T21:00:00+00:00'), create=True,
        ), patch.object(news_bot, 'render_story', side_effect=lambda card, *a: rendered.append(card) or 'card.png'), patch.object(
            news_bot, 'notify'
        ):
            news_bot.main()
        self.assertIn('اليوم', rendered[0]['title'])

    def test_ambiguous_multi_event_dates_are_rejected(self):
        story = self.story()
        story['event_date_evidence'] = 'حدث اليوم وآخر tomorrow'
        story['timing_source']['title'] = story['event_date_evidence']
        with self.assertRaisesRegex(ValueError, 'timing evidence'):
            self.prepare(story, '2026-09-10T18:00:00+00:00')

    def test_arabic_conjunction_cannot_bypass_recovery_guard(self):
        for headline in ('وغداً ينطلق السباق', 'فاليوم يبدأ السباق'):
            story = self.story()
            story['headline'] = headline
            with self.assertRaisesRegex(ValueError, 'expired'):
                self.prepare(story, '2026-09-12T10:00:00+00:00')

    def test_absolute_rewrite_retains_expiry_guard(self):
        story = self.story()
        story.update(event_date='2026-09-13', event_date_evidence='السباق في 2026-09-13')
        story['timing_source'] = {'title': story['event_date_evidence']}
        dated = self.prepare(story, '2026-09-10T10:00:00+00:00')
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.prepare(dated, '2026-09-14T10:00:00+00:00')

    def test_announcement_day_cannot_stand_in_for_event_day(self):
        story = self.story()
        story.update(event_date='2026-09-10', event_date_evidence='اليوم', headline='السباق اليوم')
        story['timing_source']['title'] = 'أعلن اليوم أن السباق غداً'
        with self.assertRaisesRegex(ValueError, 'timing evidence'):
            self.prepare(story, '2026-09-10T10:00:00+00:00')

    def test_announcement_with_prose_future_date_is_not_event_evidence(self):
        story = self.story()
        story.update(event_date='2026-09-10', event_date_evidence='أعلن المنظم اليوم', headline='ينطلق السباق اليوم')
        story['timing_source']['title'] = 'أعلن المنظم اليوم أن السباق سينطلق الأسبوع المقبل'
        with self.assertRaisesRegex(ValueError, 'timing evidence'):
            self.prepare(story, '2026-09-10T10:00:00+00:00')
