import unittest

import story_runtime as sr


class NearestStoryRepairTests(unittest.TestCase):
    def test_sama_curated_frame_assignments_are_specific(self):
        story = "قصة تأسيس مؤسسة النقد ساما"
        cases = [
            ({"heading": "نقود من فضة فقط", "text": "كانت النقود في السعودية معدنية من الفضة"}, "silver-riyal.png"),
            ({"heading": "ورقة صُنعت لأجل الحجاج", "text": "أصدرت المؤسسة إيصال الحج"}, "first-hajj-receipt.png"),
            ({"heading": "من إيصال إلى احتياطي ضخم", "text": "صار اسمها البنك المركزي السعودي"}, "sama-history-hq.jpg"),
            ({"heading": "سعر لا يتحرك", "text": "سعر صرف الريال ثابت عند 3.75 للدولار"}, "targeted-riyal-five-faisal-museum.jpg"),
        ]
        for frame, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(sr.curated_frame_visual_filename(story, frame), expected)

    def test_jeddah_curated_frame_assignments_are_specific(self):
        story = "قصة أول مطار في جدة وتطور الطيران المدني"
        cases = [
            ({"heading": "الحج كان يأتي من البحر", "text": "الوصول إلى مكة كان يبدأ من ميناء جدة"}, "jeddah-port.jpg"),
            ({"heading": "طائرة واحدة على مدرج تراب", "text": "في 1945 وصلت إلى جدة طائرة واحدة"}, "saudia-dc3-crowd.jpg"),
            ({"heading": "نهاية المطار الأول", "text": "بدأ المطار الجديد وتوقف القديم"}, "saudia-707-historic.jpg"),
        ]
        for frame, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(sr.curated_frame_visual_filename(story, frame), expected)

    def test_unrelated_frame_never_gets_a_curated_pin(self):
        self.assertIsNone(
            sr.curated_frame_visual_filename(
                "قصة تأسيس مؤسسة النقد ساما",
                {"heading": "موضوع مختلف", "text": "لا علاقة له بالعملة أو ساما"},
            )
        )


if __name__ == "__main__":
    unittest.main()
