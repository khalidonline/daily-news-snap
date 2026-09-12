import json
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import topic_bot
from daily_news_runner import remember_story_contexts, _story_for_queries


class TopicRecoveryHandoffTests(unittest.TestCase):
    def test_recovered_brief_restores_image_context_before_local_selection(self):
        brief = {
            "title": "حصيلة الضريبة",
            "body": "المصدر وزارة المالية وليس البنك المركزي.",
            "takeaway": "إيرادات الميزانية العامة",
            "source_url": "https://www.mof.gov.sa/",
            "image_queries": ["Saudi Ministry of Finance"],
            "image_queries_ar": ["وزارة المالية"],
        }
        remember_story_contexts({"stories": []})
        self.addCleanup(remember_story_contexts, {"stories": []})

        def select_photo(ar, en, path):
            context = _story_for_queries(en, ar)
            self.assertIsNotNone(context, "Recovery must not bypass the relevance selector")
            self.assertEqual(context["headline"], brief["title"])
            self.assertEqual(context["summary"], brief["body"])
            self.assertEqual(context["link"], brief["source_url"])
            return "hero.jpg", None

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(topic_bot, "OUT_DIR", Path(tmp)), \
                patch.object(topic_bot, "IMAGE_SOURCE", "auto"), \
                patch.object(topic_bot, "research", side_effect=AssertionError("No paid research")), \
                patch.object(topic_bot, "fetch_local_photo", side_effect=select_photo):
            actual, photo, _ = topic_bot.build_card("الضريبة", brief)
        self.assertEqual(actual, brief)
        self.assertEqual(photo, "hero.jpg")

    def test_exact_recovery_bypasses_schedule_only_after_delivery_dedupe(self):
        workflow = Path(".github/workflows/topic.yml").read_text(encoding="utf-8")

        self.assertIn("Check exact Topic recovery duplicate", workflow)
        self.assertIn("topic_delivery_guard.py check", workflow)
        self.assertIn("state/topic_telegram_deliveries.json", workflow)
        self.assertIn("Authorize exact Topic recovery", workflow)
        self.assertIn("github.event.action == 'topic-recovery'", workflow)
        self.assertIn("github.event.client_payload.brief_b64 != ''", workflow)
        self.assertIn("env.RECOVERY_ALREADY_DELIVERED != '1'", workflow)
        self.assertIn('echo "RUN_SCHEDULED_BOT=1" >> "$GITHUB_ENV"', workflow)
        self.assertIn('echo "SCHEDULE_SLOT_ID=" >> "$GITHUB_ENV"', workflow)
        self.assertIn("schedule gate bypassed after delivery dedupe", workflow)
        self.assertIn(
            "- name: Resolve Topic schedule slot\n"
            "        if: ${{ env.RUN_SCHEDULED_BOT == '' }}",
            workflow,
        )

    def test_workflow_bounds_topic_research_for_the_shared_daily_cap(self):
        workflow = Path(".github/workflows/topic.yml").read_text(encoding="utf-8")
        self.assertIn("TOPIC_MODEL:", workflow)
        self.assertIn("vars.TOPIC_MODEL", workflow)
        self.assertIn('MAX_TOKENS: "7000"', workflow)

    def test_workflow_requires_actual_telegram_confirmation(self):
        workflow = Path(".github/workflows/topic.yml").read_text(encoding="utf-8")
        self.assertIn('grep -Fq "telegram: sent" out/topic_run.log', workflow)
        self.assertIn("Topic card was not confirmed delivered to Telegram", workflow)
        self.assertIn("Record confirmed Topic Telegram delivery", workflow)
        self.assertIn("topic_delivery_guard.py record", workflow)

    def test_selected_topic_brief_is_saved_before_visual_search(self):
        brief = {
            "title": "عنوان محفوظ",
            "body": "تفاصيل الموضوع",
            "takeaway": "الخلاصة",
            "source_url": "https://example.com/source",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.object(topic_bot, "OUT_DIR", Path(tmp)):
            path = topic_bot.save_topic_recovery_handoff("الموضوع الأصلي", brief)
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(saved["topic"], "الموضوع الأصلي")
        self.assertEqual(saved["brief"], brief)

    def test_recoverable_visual_failure_does_not_notify_telegram(self):
        sender = Mock()
        with patch.object(topic_bot, "notify", sender):
            topic_bot.report_recoverable_topic_failure(
                "slot — no topic card: none had a usable photo"
            )
        sender.assert_not_called()

    def test_recovery_payload_reuses_exact_brief_without_research(self):
        brief = {
            "title": "العنوان نفسه",
            "body": "النص نفسه",
            "takeaway": "الخلاصة نفسها",
            "source_url": "https://example.com/source",
            "image_queries": ["exact subject"],
            "image_queries_ar": ["الموضوع نفسه"],
        }
        encoded = base64.b64encode(json.dumps({
            "topic": "الموضوع المختار",
            "brief": brief,
        }, ensure_ascii=False).encode("utf-8")).decode("ascii")
        recovered = topic_bot.load_topic_recovery_handoff(encoded)
        self.assertEqual(recovered, {"topic": "الموضوع المختار", "brief": brief})

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(topic_bot, "OUT_DIR", Path(tmp)), \
                patch.object(topic_bot, "research") as research, \
                patch.object(topic_bot, "fetch_local_photo", return_value=("hero.jpg", None)):
            actual, photo, _credit = topic_bot.build_card(
                recovered["topic"], recovered["brief"]
            )
        research.assert_not_called()
        self.assertEqual(actual, brief)
        self.assertEqual(photo, "hero.jpg")


if __name__ == "__main__":
    unittest.main()
