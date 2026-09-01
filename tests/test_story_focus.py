import tempfile
import unittest
from pathlib import Path

import story_bot as sb
import story_focus


RIYADH_STORY = "قصة الرياض: من بلدة مسورة إلى عاصمة اقتصادية"


class StorySubjectFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        story_focus.configure(sb)
        sb.load_stories()

    def test_riyadh_contract_locks_declared_subject(self):
        contract = sb.story_focus_contract(RIYADH_STORY)
        self.assertIn("Riyadh", contract)
        self.assertIn("الرياض", contract)
        self.assertIn("السفارات", contract)
        self.assertIn("ليست كافية", contract)

    def test_city_prompt_uses_city_arc_instead_of_person_arc(self):
        self.assertIn("إذا كان بطل القصة مدينة أو مكاناً", sb.SYSTEM_PROMPT)
        self.assertIn("لا تُدخل شخصاً كبطل في اللقطة الثانية", sb.SYSTEM_PROMPT)
        self.assertIn("التوسع المادي", sb.SYSTEM_PROMPT)

    def test_company_prompt_encourages_diverse_real_visual_beats(self):
        prompt = " ".join(sb.SYSTEM_PROMPT.split())
        for term in ("المنتجات", "الموظفين", "العمليات", "الفروع", "التغليف"):
            self.assertIn(term, prompt)
        self.assertIn("صور حقيقية", prompt)
        self.assertIn("لا تستخدم صوراً مولدة", prompt)

    def test_frame_visual_context_binds_story_and_specific_frame(self):
        frame = {
            "heading": "خرجت من السور",
            "text": "مع التوسع العمراني، امتدت الرياض خارج حدودها القديمة.",
        }
        context = sb.frame_visual_context(RIYADH_STORY, frame)
        self.assertIn("Riyadh", context)
        self.assertIn("الرياض", context)
        self.assertIn("خرجت من السور", context)
        self.assertIn("امتدت الرياض خارج حدودها القديمة", context)
        self.assertIn("هذه اللقطة تحديداً", context)

    def test_visual_context_prefers_image_target_over_full_timeline(self):
        frame = {
            "heading": "ما أصبحت عليه الرياض",
            "text": (
                "بدأت القصة من حدود 1902، ثم اتسعت المدينة، وفي ديسمبر 2024 "
                "افتتح مترو الرياض."
            ),
            "image_keywords": ["Riyadh Metro", "Riyadh skyline"],
            "image_keywords_ar": ["مترو الرياض", "أفق الرياض الحديث"],
        }
        context = sb.frame_visual_context(RIYADH_STORY, frame)
        self.assertIn("Riyadh Metro", context)
        self.assertIn("مترو الرياض", context)
        self.assertIn("ما أصبحت عليه الرياض", context)
        self.assertNotIn("1902", context)

    def test_renderer_context_resolves_back_to_the_frame_visual_target(self):
        frame = {
            "heading": "ما أصبحت عليه الرياض",
            "text": "افتتح مترو الرياض وأصبح جزءاً من حركة المدينة اليومية.",
            "image_keywords": ["Riyadh Metro"],
            "image_keywords_ar": ["مترو الرياض"],
        }
        renderer_context = f"{frame['heading']}\n{frame['text']}"
        matched = story_focus.frame_from_renderer_context([frame], renderer_context)
        self.assertIs(matched, frame)

    def test_city_prompt_uses_neutral_comparison_and_natural_arabic(self):
        prompt = " ".join(sb.SYSTEM_PROMPT.split())
        self.assertIn("أعلى من أي مدينة سعودية أخرى", prompt)
        self.assertIn("لا تقل", prompt)
        self.assertIn("أكثر من ثاني مدينة في القائمة", prompt)
        self.assertIn("من بلدة مسوّرة إلى مدينة بهذا الحجم", prompt)
        self.assertIn("تحولها", prompt)
        self.assertIn("صيرورتها", prompt)

    def test_city_wording_cleanup_removes_hard_ranking_and_sayrura(self):
        text = "هذه صيرورتها اليوم: 225 مليار ريال، أعلى من أي مدينة سعودية أخرى."
        cleaned = story_focus.polish_city_wording(text)
        self.assertNotIn("صيرورتها", cleaned)
        self.assertIn("تحولها", cleaned)
        self.assertNotIn("أعلى من أي مدينة سعودية أخرى", cleaned)
        self.assertIn("حجم النشاط الاقتصادي", cleaned)

    def test_runtime_visual_inventory_is_given_to_city_writer(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "approved.txt"
            index.write_text(
                "old-riyadh-souq.jpg | الرياض القديمة, old Riyadh, سوق تقليدي | Wikimedia\n"
                "riyadh-1975-construction.jpg | الرياض, البناء, السبعينات | أرشيف\n"
                "riyadh-1977-construction.jpg | الرياض, 1977, عمران | أرشيف\n"
                "mcdonalds-riyadh-first.jpg | ماكدونالدز, أول فرع, الرياض | أرشيف\n",
                encoding="utf-8",
            )
            prompt = story_focus.runtime_visual_inventory_prompt(index)
        self.assertIn("صور محلية مراجعة", prompt)
        self.assertIn("old-riyadh-souq.jpg", prompt)
        self.assertIn("riyadh-1975-construction.jpg", prompt)
        self.assertIn("البناء", prompt)
        self.assertIn("ليست مصادر للحقائق", prompt)
        self.assertIn("مرحلة مهمة", prompt)
        self.assertIn("image_keywords", prompt)

    def test_inventory_prompt_requires_the_frame_beat_to_be_visible(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "approved.txt"
            index.write_text(
                "riyadh-1975-construction.jpg | الرياض, البناء, السبعينات | أرشيف الرياض التاريخي\n",
                encoding="utf-8",
            )
            prompt = story_focus.runtime_visual_inventory_prompt(index)
        self.assertIn("الفكرة المركزية", prompt)
        self.assertIn("ما يظهر في الصورة", prompt)
        self.assertIn("لا يكفي", prompt)

    def test_story_inventory_excludes_unrelated_catalogue_rows(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "approved.txt"
            index.write_text(
                "riyadh-skyline.jpg | الرياض, Riyadh, skyline | Wikimedia\n"
                "tokyo-crossing.jpg | طوكيو, Tokyo, crossing | Wikimedia\n",
                encoding="utf-8",
            )
            prompt = story_focus.runtime_visual_inventory_prompt(index, aliases=["الرياض", "Riyadh"])
        self.assertIn("riyadh-skyline.jpg", prompt)
        self.assertNotIn("tokyo-crossing.jpg", prompt)

    def test_reviewed_archive_year_is_authoritative_in_vision_context(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "approved.txt"
            index.write_text(
                "riyadh-1975-construction.jpg | الرياض, البناء, السبعينات | أرشيف الرياض التاريخي\n",
                encoding="utf-8",
            )
            frame = {
                "subject_kind": "place_city",
                "heading": "توسع عمراني في السبعينات",
                "text": "اتسعت الرياض سريعاً مع موجة بناء جديدة.",
                "image_keywords": ["Riyadh 1975 construction"],
                "image_keywords_ar": ["الرياض", "البناء", "السبعينات"],
            }
            note = story_focus.reviewed_local_provenance(Path(td) / "riyadh-1975-construction.jpg", frame, index)
        self.assertIn("1975", note)
        self.assertIn("مراجعة", note)
        self.assertIn("لا تستنتج سنة مختلفة", note)
        self.assertIn("البناء", note)

    def test_unlisted_photo_gets_no_reviewed_provenance_override(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "approved.txt"
            index.write_text("riyadh-1975-construction.jpg | الرياض, البناء, السبعينات | أرشيف\n", encoding="utf-8")
            note = story_focus.reviewed_local_provenance(Path(td) / "downloaded-web-photo.jpg", {}, index)
        self.assertEqual("", note)

    def test_city_local_search_can_match_arabic_catalog_tags(self):
        brief = {"frames": [{"subject_kind": "place_city", "image_keywords": ["Riyadh 1970s construction"], "image_keywords_ar": ["الرياض", "البناء", "السبعينات"]}]}
        prepared = story_focus.prepare_city_visual_search(brief)
        keywords = prepared["frames"][0]["image_keywords"]
        self.assertIn("Riyadh 1970s construction", keywords)
        self.assertIn("الرياض", keywords)
        self.assertIn("البناء", keywords)
        self.assertIn("السبعينات", keywords)

    def test_city_search_appends_declared_city_aliases_as_simple_fallback(self):
        brief = {"story": RIYADH_STORY, "frames": [{"subject_kind": "place_city", "image_keywords": ["Riyadh 1970s construction"], "image_keywords_ar": ["البناء", "السبعينات"]}]}
        prepared = story_focus.prepare_city_visual_search(brief, aliases=["Riyadh", "الرياض"])
        keywords = prepared["frames"][0]["image_keywords"]
        self.assertEqual("Riyadh 1970s construction", keywords[0])
        self.assertIn("Riyadh", keywords)
        self.assertIn("الرياض", keywords)
        self.assertLessEqual(len(keywords), 6)

    def test_city_fallback_accepts_relevant_neutral_but_never_wrong_city(self):
        self.assertTrue(story_focus.city_photo_verdict_ok("yes"))
        self.assertTrue(story_focus.city_photo_verdict_ok("neutral"))
        self.assertFalse(story_focus.city_photo_verdict_ok("no"))
        self.assertFalse(story_focus.city_photo_verdict_ok(""))

    def test_subject_alias_matches_inside_specific_catalog_tag(self):
        self.assertTrue(story_focus.catalog_tags_match_aliases(["Riyadh skyline", "real estate"], ["Riyadh", "الرياض"]))
        self.assertTrue(story_focus.catalog_tags_match_aliases(["أفق الرياض الحديث"], ["Riyadh", "الرياض"]))
        self.assertFalse(story_focus.catalog_tags_match_aliases(["Jeddah skyline", "جدة"], ["Riyadh", "الرياض"]))

    def test_city_deck_needs_four_matched_visual_slots(self):
        brief = {"frames": [{"subject_kind": "place_city"} for _ in range(6)]}
        self.assertFalse(story_focus.city_deck_visuals_ready(brief, [object(), None, None, None, None, None]))
        self.assertTrue(story_focus.city_deck_visuals_ready(brief, [object(), object(), object(), object(), None, None]))

    def test_story_photo_gate_requires_confirmed_relevance(self):
        self.assertTrue(sb.story_photo_verdict_ok("yes"))
        self.assertFalse(sb.story_photo_verdict_ok("neutral"))
        self.assertFalse(sb.story_photo_verdict_ok("no"))
        self.assertFalse(sb.story_photo_verdict_ok(""))

    def test_configuration_is_idempotent(self):
        first_prompt = sb.SYSTEM_PROMPT
        first_gate = sb.photo_shows
        story_focus.configure(sb)
        self.assertEqual(first_prompt, sb.SYSTEM_PROMPT)
        self.assertIs(first_gate, sb.photo_shows)


if __name__ == "__main__":
    unittest.main()
