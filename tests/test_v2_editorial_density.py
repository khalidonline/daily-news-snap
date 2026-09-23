import unittest
from publishing_v2.autopilot.policy import validate_draft
from test_v2_autopilot import draft, research


class EditorialDensityTests(unittest.TestCase):
    def test_rejects_observed_aircraft_code_overload(self):
        data = draft()
        data['cards'][0]['body'] = 'بدأ الطلب على UH-1 ضمن برنامج UTTAS مع محرك T700.'
        data['cards'][1]['body'] = 'طار YUH-60A ونافس YUH-61A ثم اختير UH-60.'
        with self.assertRaisesRegex(ValueError, 'technical_identifier_overload'):
            validate_draft(data, research())

    def test_allows_a_few_essential_models_and_dates(self):
        data = draft()
        data['cards'][0]['body'] = 'بدأت F-35 عام 2006 وتطورت عن F-16.'
        data['cards'][1]['body'] = 'انتشرت F-35 بين دول أكثر بحلول 2024.'
        validate_draft(data, research())

    def test_ignores_search_metadata_and_counts_repeated_subject_once(self):
        data = draft()
        for card in data['cards']:
            card['title'] = 'قصة UH-60'
            card['body'] = 'كيف تطورت UH-60 مع الوقت؟'
            card['image_query'] = 'UH-1 T700 YUH-60A YUH-61A UH-60'
        validate_draft(data, research())

    def test_checks_punch_and_caption_not_only_body(self):
        data = draft()
        data['cards'][0]['title'] = 'UH-1 وT700'
        data['cards'][1]['punch'] = 'YUH-60A'
        data['cards'][1]['image_caption'] = 'YUH-61A'
        with self.assertRaisesRegex(ValueError, 'technical_identifier_overload'):
            validate_draft(data, research())
