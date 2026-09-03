import os
import unittest

try:
    import story_quality_gate as sqg
except ImportError:
    sqg = None


def frame(heading, text, keywords=None, punch=""):
    return {
        "heading": heading,
        "text": text,
        "punch": punch,
        "subject_kind": "historical",
        "image_keywords": list(keywords or []),
        "image_keywords_ar": [],
    }


def state_for(frames, visual_labels=None):
    visual_labels = visual_labels or {}
    rows = {}
    for index, payload in enumerate(frames, 1):
        row = {
            "status": "PASS",
            "image_source": f"state/story_visuals/test/assets/frame-{index:02d}.jpg",
            "frame_payload": payload,
        }
        if index in visual_labels:
            row["visual_evidence"] = visual_labels[index]
        rows[str(index)] = row
    return {"story": "fixture", "frames": rows}


def airport_frames():
    return [
        frame("بداية مطار جدة", "بدأ مطار جدة بمدرج بسيط ومرافق محدودة.", ["Jeddah airport historic 1945"]),
        frame("1945 وبداية الطيران", "في 1945 دخل الطيران المدني في جدة مرحلة جديدة.", ["Jeddah airport DC-3 1945"]),
        frame("المطار يتوسع", "مع زيادة الرحلات توسع مطار جدة لخدمة حركة أكبر.", ["Jeddah airport 1960"]),
        frame("1981 والانتقال", "في 1981 افتتح مطار الملك عبدالعزيز الدولي في جدة.", ["Jeddah airport 1981"]),
        frame("مرحلة التوسع الحديثة", "واصل مطار جدة توسعه مع نمو حركة السفر.", ["Jeddah airport Terminal 1 modern"]),
        frame("مطار جدة اليوم", "اليوم أصبح مطار جدة بوابة جوية حديثة في السعودية.", ["King Abdulaziz International Airport Terminal 1 current"]),
    ]


def company_frames():
    return [
        frame("بداية شركة أكمي", "بدأت شركة أكمي بمنتج واحد في السوق المحلي.", ["Acme company 1980"]),
        frame("أكمي تتوسع", "وسعت شركة أكمي أعمالها بعد نجاح المنتج الأول.", ["Acme factory 1990"]),
        frame("مرحلة جديدة", "دخلت أكمي سوقاً جديداً وغيرت نموذج أعمالها.", ["Acme operations 2000"]),
        frame("أكمي عالمياً", "أصبحت شركة أكمي تبيع في أسواق خارجية.", ["Acme company 2010"]),
        frame("التحول الرقمي", "استثمرت أكمي في قنوات رقمية وخدمات جديدة.", ["Acme digital modern"]),
        frame("أكمي اليوم", "اليوم تعمل أكمي بنموذج أكثر تنوعاً وحداثة.", ["Acme headquarters current 2025"]),
    ]


@unittest.skipIf(sqg is None, "story_quality_gate not implemented yet")
class StoryQualityGateTests(unittest.TestCase):
    def assertFinding(self, report, dimension, frame_no=None, code=None):
        matches = [
            item for item in report.get("findings", [])
            if item.get("dimension") == dimension
            and (frame_no is None or item.get("frame") == frame_no)
            and (code is None or item.get("code") == code)
        ]
        self.assertTrue(matches, report)

    def test_focused_chronological_airport_story_passes(self):
        frames = airport_frames()
        report = sqg.evaluate_story_quality(
            "قصة تطور مطار جدة والطيران المدني", frames, state_for(frames)
        )
        self.assertTrue(sqg.release_ready(report), report)
        self.assertEqual("PASS", report["status"])

    def test_airport_story_that_turns_into_makkah_travel_is_blocked(self):
        frames = airport_frames()
        frames[0] = frame(
            "الحج كان يأتي من البحر",
            "كان القادمون إلى مكة يصلون عبر البحر قبل أن يكملوا رحلتهم إلى مكة.",
            ["Jeddah port historic"],
        )
        frames[5] = frame(
            "بوابة مكة تغيّرت",
            "اليوم يبدأ القادم إلى مكة رحلته من بوابة مختلفة.",
            ["Makkah pilgrims current"],
        )
        report = sqg.evaluate_story_quality(
            "قصة تطور مطار جدة والطيران المدني", frames, state_for(frames)
        )
        self.assertFalse(sqg.release_ready(report))
        self.assertFinding(report, "subject_focus", 1)
        self.assertFinding(report, "subject_focus", 6)

    def test_company_story_with_unrelated_founder_tangent_is_blocked(self):
        frames = company_frames()
        frames[2] = frame(
            "طفولة المؤسس",
            "عاش المؤسس مع أسرته ودرس في مدرسة صغيرة قبل سنوات من تأسيس العمل.",
            ["founder childhood family portrait"],
        )
        report = sqg.evaluate_story_quality("قصة شركة أكمي وتطورها", frames, state_for(frames))
        self.assertFalse(sqg.release_ready(report))
        self.assertFinding(report, "subject_focus", 3)

    def test_one_supporting_transition_can_pass_when_story_returns_to_subject(self):
        frames = company_frames()
        frames[2] = frame(
            "السوق يتغير",
            "ولهذا تغيرت عادات الشراء بسرعة وأصبح التوزيع التقليدي أقل كفاءة.",
            ["retail market transition 2000"],
        )
        report = sqg.evaluate_story_quality("قصة شركة أكمي وتطورها", frames, state_for(frames))
        self.assertTrue(sqg.release_ready(report), report)
        self.assertEqual("SUPPORTING", report["frame_evidence"][2]["focus"])

    def test_unsupported_exclusivity_claim_is_blocked(self):
        frames = airport_frames()
        frames[1]["text"] += " وكان هذا الطريق الوحيد للوصول إلى مكة."
        report = sqg.evaluate_story_quality(
            "قصة تطور مطار جدة والطيران المدني", frames, state_for(frames)
        )
        self.assertFinding(report, "claim_precision", 2, "UNSUPPORTED_EXCLUSIVITY")

    def test_saudi_context_uses_saudi_not_ambiguous_aljazira(self):
        frames = airport_frames()
        frames[1]["text"] = "في 1945 بدأت مرحلة جديدة للطيران المدني في الجزيرة."
        report = sqg.evaluate_story_quality(
            "قصة تطور مطار جدة والطيران المدني في السعودية", frames, state_for(frames)
        )
        self.assertFinding(report, "claim_precision", 2, "SAUDI_GEOGRAPHY_AMBIGUOUS")

    def test_explicit_date_regression_without_flashback_is_blocked(self):
        frames = airport_frames()
        frames[4]["text"] = "في 2020 دخل مطار جدة مرحلة توسع جديدة."
        frames[5]["text"] = "في 1975 بدأ التخطيط لمرحلة مختلفة في مطار جدة."
        frames[5]["image_keywords"] = ["Jeddah airport 1975 archive"]
        report = sqg.evaluate_story_quality(
            "قصة تطور مطار جدة والطيران المدني", frames, state_for(frames)
        )
        self.assertFinding(report, "narrative_chronology", 6, "UNEXPLAINED_TIME_REGRESSION")

    def test_explicit_flashback_allows_date_regression(self):
        frames = airport_frames()
        frames[4]["text"] = "في 2020 دخل مطار جدة مرحلة توسع جديدة."
        frames[5]["text"] = "وبالعودة إلى 1975، بدأ التخطيط الذي مهّد لتطور مطار جدة لاحقاً."
        frames[5]["image_keywords"] = ["Jeddah airport archive 1975"]
        report = sqg.evaluate_story_quality(
            "قصة تطور مطار جدة والطيران المدني", frames, state_for(frames)
        )
        self.assertFalse(any(
            f.get("code") == "UNEXPLAINED_TIME_REGRESSION"
            for f in report["findings"]
        ), report)

    def test_current_final_frame_with_archival_visual_is_blocked(self):
        frames = airport_frames()
        frames[-1]["image_keywords"] = ["Jeddah airport historic archive 1981"]
        report = sqg.evaluate_story_quality(
            "قصة تطور مطار جدة والطيران المدني", frames, state_for(frames)
        )
        self.assertFinding(report, "final_frame_currency", 6, "CURRENT_COPY_ARCHIVAL_VISUAL")

    def test_current_final_frame_with_unknown_visual_age_fails_closed(self):
        frames = airport_frames()
        frames[-1]["image_keywords"] = ["King Abdulaziz International Airport Jeddah"]
        report = sqg.evaluate_story_quality(
            "قصة تطور مطار جدة والطيران المدني", frames, state_for(frames)
        )
        self.assertFinding(report, "final_frame_currency", 6, "CURRENT_COPY_UNPROVEN_VISUAL")

    def test_current_final_frame_with_modern_evidence_passes(self):
        frames = airport_frames()
        frames[-1]["image_keywords"] = ["King Abdulaziz International Airport Terminal 1 current 2025"]
        report = sqg.evaluate_story_quality(
            "قصة تطور مطار جدة والطيران المدني", frames, state_for(frames)
        )
        self.assertFalse(any(
            f.get("dimension") == "final_frame_currency"
            for f in report["findings"]
        ), report)

    def test_timeless_frame_can_use_unknown_visual_era(self):
        frames = company_frames()
        frames[2]["text"] = "تعتمد أكمي على شبكة توزيع تربط منتجاتها بالمتاجر."
        frames[2]["image_keywords"] = ["Acme distribution network"]
        report = sqg.evaluate_story_quality("قصة شركة أكمي وتطورها", frames, state_for(frames))
        self.assertFalse(any(
            f.get("frame") == 3 and f.get("dimension") == "visual_chronology"
            for f in report["findings"]
        ), report)

    def test_visual_failure_returns_only_affected_frame_repair_target(self):
        frames = airport_frames()
        frames[-1]["image_keywords"] = ["Jeddah airport historic archive 1981"]
        report = sqg.evaluate_story_quality(
            "قصة تطور مطار جدة والطيران المدني", frames, state_for(frames)
        )
        repair = sqg.repair_target(report)
        self.assertEqual([6], repair["frames"])
        self.assertEqual("visual_only", repair["frame_modes"]["6"])

    def test_quality_evaluator_requires_no_model_or_network_credentials(self):
        frames = airport_frames()
        saved = {key: os.environ.pop(key, None) for key in (
            "ANTHROPIC_API_KEY", "ARK_API_KEY", "OPENAI_API_KEY", "TELEGRAM_TOKEN"
        )}
        try:
            report = sqg.evaluate_story_quality(
                "قصة تطور مطار جدة والطيران المدني", frames, state_for(frames)
            )
            self.assertIn(report["status"], {"PASS", "BLOCKED"})
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
