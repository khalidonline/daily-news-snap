import unittest

import guarded_story_publish as gsp


def _frame(heading, text, keywords):
    return {
        "heading": heading,
        "text": text,
        "punch": "",
        "image_keywords": list(keywords),
        "image_keywords_ar": [],
    }


def _ready_state(drift=False):
    frames = [
        _frame("بداية مطار جدة", "بدأ مطار جدة بمدرج بسيط.", ["Jeddah airport historic 1945"]),
        _frame("1945 والطيران", "في 1945 دخل الطيران المدني في جدة مرحلة جديدة.", ["Jeddah airport 1945"]),
        _frame("المطار يتوسع", "توسع مطار جدة مع زيادة الرحلات.", ["Jeddah airport 1960"]),
        _frame("1981 والانتقال", "في 1981 افتتح مطار الملك عبدالعزيز في جدة.", ["Jeddah airport 1981"]),
        _frame("مرحلة حديثة", "واصل مطار جدة توسعه بخدمات أحدث.", ["Jeddah airport Terminal 1 modern"]),
        _frame("مطار جدة اليوم", "اليوم أصبح مطار جدة بوابة حديثة في السعودية.", ["Jeddah airport Terminal 1 current 2025"]),
    ]
    if drift:
        frames[0] = _frame(
            "الحج كان يأتي من البحر",
            "كان القادمون إلى مكة يصلون عبر البحر قبل إكمال رحلتهم.",
            ["Jeddah port historic"],
        )
    return {
        "story": "قصة تطور مطار جدة والطيران المدني",
        "frames": {
            str(i): {
                "status": "PASS",
                "image_source": f"state/story_visuals/test/assets/frame-{i}.jpg",
                "frame_payload": payload,
            }
            for i, payload in enumerate(frames, 1)
        },
    }


class StoryQualityGateIntegrationTests(unittest.TestCase):
    def test_technical_ready_and_quality_pass_remains_ready(self):
        saved = []
        status, report, updated = gsp.apply_quality_gate(
            "قصة تطور مطار جدة والطيران المدني",
            "rev-pass",
            _ready_state(),
            technical_status="READY",
            save_fn=lambda story, revision, state: saved.append((story, revision, state)),
        )
        self.assertEqual("READY", status)
        self.assertEqual("PASS", report["status"])
        self.assertEqual("PASS", updated["story_quality_status"])
        self.assertEqual(1, len(saved))

    def test_technical_ready_is_downgraded_when_quality_blocks(self):
        status, report, updated = gsp.apply_quality_gate(
            "قصة تطور مطار جدة والطيران المدني",
            "rev-block",
            _ready_state(drift=True),
            technical_status="READY",
            save_fn=lambda *_args: None,
        )
        self.assertEqual("REVIEW", status)
        self.assertEqual("BLOCKED", report["status"])
        self.assertEqual("BLOCKED", updated["story_quality_status"])
        self.assertTrue(updated["story_quality_repair"]["frames"])

    def test_existing_technical_review_never_becomes_ready(self):
        status, report, _updated = gsp.apply_quality_gate(
            "قصة تطور مطار جدة والطيران المدني",
            "rev-review",
            _ready_state(),
            technical_status="REVIEW",
            save_fn=lambda *_args: None,
        )
        self.assertEqual("REVIEW", status)
        self.assertEqual("PASS", report["status"])

    def test_quality_evidence_is_persisted_before_review_boundary(self):
        saved = []
        gsp.apply_quality_gate(
            "قصة تطور مطار جدة والطيران المدني",
            "rev-evidence",
            _ready_state(drift=True),
            technical_status="READY",
            save_fn=lambda story, revision, state: saved.append(state.copy()),
        )
        self.assertEqual(1, len(saved))
        self.assertEqual("story-quality-v1", saved[0]["story_quality_policy"])
        self.assertEqual("BLOCKED", saved[0]["story_quality_status"])
        self.assertIsInstance(saved[0]["story_quality_findings"], list)
        self.assertIn("frames", saved[0]["story_quality_repair"])


if __name__ == "__main__":
    unittest.main()
