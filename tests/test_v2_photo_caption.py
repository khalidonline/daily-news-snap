import unittest
from test_v2_autopilot import draft, research
from publishing_v2.autopilot.policy import validate_draft

class PhotoCaptionDraftTests(unittest.TestCase):
    def test_optional_story_caption_survives_validation(self):
        value = draft()
        value['cards'][1]['image_caption'] = 'صورة توضيحية للكارتينج'
        validate_draft(value, research())
        self.assertEqual(value['cards'][1]['image_caption'], 'صورة توضيحية للكارتينج')

    def test_invalid_caption_is_rejected_before_rendering(self):
        for kind, caption in [('info', 'صورة توضيحية'), ('story', ['text']), ('story', 'x'*51), ('story', '')]:
            with self.subTest(kind=kind, caption=caption):
                value = draft()
                value['cards'][0 if kind == 'info' else 1]['image_caption'] = caption
                with self.assertRaises(ValueError):
                    validate_draft(value, research())
