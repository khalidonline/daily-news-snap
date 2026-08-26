import unittest

from tools.bulk_visual_register import add_logo_domain_to_story_text


class TypedLogoRegistrationTests(unittest.TestCase):
    def test_logo_is_standalone_segment_after_typed_entity(self):
        story = "سليمان الراجحي: من حمّال في السوق إلى مؤسس أكبر بنك ثم تبرّع بثروته"
        text = (
            story
            + " | person: سليمان الراجحي, Sulaiman Al Rajhi"
            + " | entity: مصرف الراجحي\n"
        )
        updated = add_logo_domain_to_story_text(text, story, "alrajhibank.com.sa")
        self.assertIn("| entity: مصرف الراجحي | logo:alrajhibank.com.sa", updated)
        self.assertNotIn("entity: مصرف الراجحي, logo:", updated)

    def test_existing_malformed_typed_logo_is_normalized(self):
        story = "صالح الراجحي: الشريك الذي بنى المؤسسة وابتعد عن الأضواء"
        text = (
            story
            + " | person: صالح الراجحي, Saleh Al Rajhi"
            + " | entity: مصرف الراجحي, logo:alrajhibank.com.sa\n"
        )
        updated = add_logo_domain_to_story_text(text, story, "alrajhibank.com.sa")
        self.assertIn("| entity: مصرف الراجحي | logo:alrajhibank.com.sa", updated)
        self.assertEqual(updated.count("logo:alrajhibank.com.sa"), 1)


if __name__ == "__main__":
    unittest.main()
