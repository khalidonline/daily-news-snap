import json
import os
import tempfile
import types
import unittest

import story_brief_store as sbs
import story_cost_guard as scg
import story_editorial_runtime as ser


def good_brief():
    return {
        "frames": [
            {
                "heading": f"مشهد {i}",
                "text": f"نص واضح ومختلف للقطة رقم {i} يشرح تطور القصة بشكل مباشر.",
                "punch": f"خلاصة واضحة {i}",
                "subject_kind": "company",
                "image_keywords": [f"subject {i}"],
                "image_keywords_ar": [f"موضوع {i}"],
            }
            for i in range(1, 7)
        ],
        "sources": ["https://example.com/source"],
    }


class FakeStoryBot:
    SYSTEM_PROMPT = "prompt {n}"
    STORY_MODEL = "claude-opus-5"
    STORY_FRAMES = 6

    def __init__(self, brief=None):
        self.calls = 0
        self.brief = brief if brief is not None else good_brief()
        self._LAST_EDITORIAL_USAGE = {}

    def research(self, story):
        self.calls += 1
        self._LAST_EDITORIAL_USAGE = {
            "message_id": f"msg_{self.calls}",
            "input_tokens": 100,
            "output_tokens": 50,
        }
        return json.loads(json.dumps(self.brief, ensure_ascii=False))


class _FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class FakeHttpStoryBot(FakeStoryBot):
    def __init__(self):
        super().__init__()
        self.http_successes = 0

        def urlopen(*args, **kwargs):
            self.http_successes += 1
            return _FakeResponse({
                "id": f"msg_http_{self.http_successes}",
                "usage": {"input_tokens": 20, "output_tokens": 10},
                "content": [],
            })

        self.urllib = types.SimpleNamespace(
            request=types.SimpleNamespace(urlopen=urlopen)
        )

    def research(self, story):
        # Simulate the real research path needing a second successful Messages
        # response (pause_turn/truncation continuation). The cost wrapper must
        # stop before the second successful paid response is purchased.
        with self.urllib.request.urlopen("request-1") as response:
            response.read()
        with self.urllib.request.urlopen("request-2") as response:
            response.read()
        return good_brief()


class EditorialRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp_briefs = tempfile.TemporaryDirectory()
        self.tmp_cost = tempfile.TemporaryDirectory()
        self.saved = {key: os.environ.get(key) for key in (
            "STORY_BRIEF_ROOT", "STORY_COST_STATE_ROOT", "STORY_OPERATION_MODE",
            "STORY_REGENERATION_NONCE",
        )}
        os.environ["STORY_BRIEF_ROOT"] = self.tmp_briefs.name
        os.environ["STORY_COST_STATE_ROOT"] = self.tmp_cost.name
        os.environ["STORY_OPERATION_MODE"] = "auto"
        os.environ.pop("STORY_REGENERATION_NONCE", None)

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp_briefs.cleanup()
        self.tmp_cost.cleanup()

    def test_first_auto_call_generates_once_then_second_run_hits_cache(self):
        sb = FakeStoryBot()
        ser.configure(sb)
        first = sb.research("قصة اختبار")
        second = sb.research("قصة اختبار")
        self.assertEqual(1, sb.calls)
        self.assertEqual(first, second)
        rows = [json.loads(line) for line in scg.usage_ledger_path().read_text(encoding="utf-8").splitlines()]
        self.assertEqual(1, sum(row.get("event") == "model_result" for row in rows))
        self.assertEqual(1, sum(row.get("event") == "cache_hit" for row in rows))

    def test_visual_only_cache_hit_makes_zero_additional_calls(self):
        sb = FakeStoryBot()
        ser.configure(sb)
        expected = sb.research("قصة اختبار")
        os.environ["STORY_OPERATION_MODE"] = "visual_only"
        actual = sb.research("قصة اختبار")
        self.assertEqual(expected, actual)
        self.assertEqual(1, sb.calls)

    def test_visual_only_cache_miss_blocks_before_paid_call(self):
        sb = FakeStoryBot()
        ser.configure(sb)
        os.environ["STORY_OPERATION_MODE"] = "visual_only"
        with self.assertRaises(SystemExit):
            sb.research("قصة غير مخزنة")
        self.assertEqual(0, sb.calls)

    def test_quality_failure_does_not_cache_or_retry(self):
        weak = good_brief()
        weak["sources"] = []
        sb = FakeStoryBot(weak)
        ser.configure(sb)
        with self.assertRaises(SystemExit):
            sb.research("قصة ضعيفة")
        self.assertEqual(1, sb.calls)
        revision = ser.revision_for(sb, "قصة ضعيفة", "auto")
        self.assertIsNone(sbs.load_locked_brief("قصة ضعيفة", revision))
        with self.assertRaises(scg.EditorialSpendBlocked):
            sb.research("قصة ضعيفة")
        self.assertEqual(1, sb.calls)

    def test_corrupt_cache_blocks_instead_of_regenerating(self):
        sb = FakeStoryBot()
        ser.configure(sb)
        revision = ser.revision_for(sb, "قصة اختبار", "auto")
        path = sbs.brief_path("قصة اختبار", revision)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(sbs.BriefCacheError):
            sb.research("قصة اختبار")
        self.assertEqual(0, sb.calls)

    def test_explicit_regeneration_uses_distinct_revision(self):
        sb = FakeStoryBot()
        ser.configure(sb)
        sb.research("قصة اختبار")
        base_revision = ser.revision_for(sb, "قصة اختبار", "auto")
        os.environ["STORY_OPERATION_MODE"] = "regenerate_editorial"
        os.environ["STORY_REGENERATION_NONCE"] = "run-123"
        regen_revision = ser.revision_for(sb, "قصة اختبار", "regenerate_editorial")
        self.assertNotEqual(base_revision, regen_revision)
        sb.research("قصة اختبار")
        self.assertEqual(2, sb.calls)
        self.assertIsNotNone(sbs.load_locked_brief("قصة اختبار", regen_revision))

    def test_second_successful_anthropic_response_is_blocked(self):
        sb = FakeHttpStoryBot()
        ser.configure(sb)
        with self.assertRaises(scg.EditorialSpendBlocked):
            sb.research("قصة تحتاج متابعة")
        self.assertEqual(1, sb.http_successes)
        rows = [json.loads(line) for line in scg.usage_ledger_path().read_text(encoding="utf-8").splitlines()]
        model_rows = [row for row in rows if row.get("event") == "model_result"]
        self.assertEqual(1, len(model_rows))
        self.assertEqual("msg_http_1", model_rows[0]["message_id"])

    def test_revision_prompt_receives_the_active_story(self):
        sb = FakeStoryBot()
        seen = []

        def prompt_for_revision():
            seen.append(getattr(sb, "_ACTIVE_EDITORIAL_STORY", ""))
            return "prompt {n}"

        sb.editorial_prompt_for_revision = prompt_for_revision
        ser.configure(sb)
        sb.research("قصة الرياض")

        self.assertTrue(seen)
        self.assertTrue(all(story == "قصة الرياض" for story in seen))


if __name__ == "__main__":
    unittest.main()
