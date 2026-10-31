import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import topic_snapchat
from daily_news_runner import _story_for_queries, remember_story_contexts
from topic_snapchat import install, prepare_shortlist, research_with_validation


class TopicSnapchatRuntimeTests(unittest.TestCase):
    def test_selector_offers_live_event_and_hands_source_to_research(self):
        import io
        import json
        from datetime import datetime, timezone
        event = {"title": "Apple announces a major product", "summary": "A confirmed price change",
                 "source": "Example", "link": "https://example.com/launch",
                 "lane": "business_tech", "published_at": datetime.now(timezone.utc).isoformat()}
        bot = SimpleNamespace(load_topics=lambda: [{"topic": "Evergreen"}], load_used=lambda: [],
            FORCE_SEASON="", fetch_headlines=lambda: [event], score_topics=lambda *a: [],
            report_shortlist=lambda *a: None, ANTHROPIC_API_KEY="test", SELECT_MODEL="test",
            SELECT_PROMPT="select", TOPIC_SELECT_MAX_PAID_RESPONSES=1, MODEL_MAX_USD_PER_RUN=0)
        response = {"content": [{"type": "text", "text": '{"index":0,"why":"timely explainer"}'}]}
        with patch.object(topic_snapchat, "prepare_shortlist", return_value=[]), \
             patch.object(topic_snapchat.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as call, \
             patch.object(topic_snapchat.model_meter, "require_response_capacity"), \
             patch.object(topic_snapchat.model_meter, "record_anthropic_response"), \
             patch.object(topic_snapchat.model_meter, "note_successful_response"):
            selected = topic_snapchat._make_choose_topic(bot)()
        self.assertEqual(selected, "ما وراء الخبر: " + event["title"])
        self.assertEqual(bot._TOPIC_EVENTS[selected]["link"], event["link"])
        self.assertEqual(call.call_count, 1)
        payload = json.loads(call.call_args.args[0].data)
        self.assertIn(event["published_at"], payload["messages"][0]["content"])

    def test_no_event_uses_catalog_and_clears_previous_event_context(self):
        bot = SimpleNamespace(load_topics=lambda: [{"topic": "Evergreen"}], load_used=lambda: [],
            FORCE_SEASON="", fetch_headlines=lambda: [],
            score_topics=lambda *a: [{"topic": "Evergreen", "score": 5}],
            report_shortlist=lambda *a: None, ANTHROPIC_API_KEY="",
            _TOPIC_EVENTS={"Previous": {"title": "old event"}})
        with patch.object(topic_snapchat, "prepare_shortlist", return_value=[{"topic": "Evergreen"}]):
            self.assertEqual(topic_snapchat._make_choose_topic(bot)(), "Evergreen")
        self.assertEqual(bot._TOPIC_EVENTS, {})

    def test_event_candidates_exclude_stale_undated_and_used_topics(self):
        from datetime import datetime, timezone
        now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
        def item(title, published):
            return {"title": title, "summary": "A major consumer product change",
                    "source": "Example", "link": "https://example.com/" + title,
                    "lane": "business_tech", "published_at": published}
        items = [item("Apple launch", "2026-09-10T10:00:00+00:00"),
                 item("Old launch", "2026-09-06T10:00:00+00:00"),
                 item("Undated launch", None),
                 item("Future launch", "2026-09-11T10:00:00+00:00")]
        rows = topic_snapchat.event_topic_candidates(items, set(), now=now)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"]["link"], "https://example.com/Apple launch")
        self.assertEqual(topic_snapchat.event_topic_candidates(items, {rows[0]["topic"]}, now=now), [])

    def test_event_research_receives_source_context_and_restores_prompt(self):
        bot = SimpleNamespace(SYSTEM_PROMPT="base", _TOPIC_EVENTS={
            "Chosen": {"title": "Apple {launch}", "source": "Example",
                       "link": "https://example.com/launch", "published_at": "2026-09-10T10:00:00Z"}})
        received = []
        def research(topic):
            received.append((topic, bot.SYSTEM_PROMPT.format(n=3)))
            return {"title": "Draft"}
        with patch.object(topic_snapchat, "research_with_validation", side_effect=lambda b, fn, t: fn(t)):
            topic_snapchat.research_for_event(bot, research, "Chosen")
            topic_snapchat.research_for_event(bot, research, "Manual unrelated")
        self.assertIn("https://example.com/launch", received[0][1])
        self.assertEqual(received[0][0], "Chosen")
        self.assertEqual(received[1][1], "base")
        self.assertEqual(bot.SYSTEM_PROMPT, "base")

    def test_event_research_restores_prompt_after_failure(self):
        bot = SimpleNamespace(SYSTEM_PROMPT="base", _TOPIC_EVENTS={"Chosen": {"title": "event"}})
        with patch.object(topic_snapchat, "research_with_validation", side_effect=RuntimeError("failed")):
            with self.assertRaises(RuntimeError):
                topic_snapchat.research_for_event(bot, lambda t: {}, "Chosen")
        self.assertEqual(bot.SYSTEM_PROMPT, "base")

    def test_prepare_shortlist_uses_bounded_performance_and_categories(self):
        with tempfile.TemporaryDirectory() as td:
            topics_path = Path(td) / "topics.txt"
            topics_path.write_text(
                "# ═══ المال الشخصي ═══\nمال 1\nمال 2\n"
                "# ═══ التقنية ═══\nتقنية\n",
                encoding="utf-8",
            )
            bot = SimpleNamespace(TOPICS_FILE=topics_path)
            scored = [
                {"topic": "مال 1", "score": 5, "reasons": ["من القائمة العامة"]},
                {"topic": "مال 2", "score": 5, "reasons": ["من القائمة العامة"]},
                {"topic": "تقنية", "score": 5, "reasons": ["من القائمة العامة"]},
            ]
            shortlist = prepare_shortlist(bot, scored, {"categories": {"التقنية": 4}}, limit=3)
        self.assertEqual(shortlist[0]["topic"], "تقنية")
        self.assertEqual({row["category"] for row in shortlist}, {"المال الشخصي", "التقنية"})

    def test_research_validation_retries_once(self):
        calls = []
        bot = SimpleNamespace(SYSTEM_PROMPT="base prompt")

        def original(topic):
            calls.append((topic, bot.SYSTEM_PROMPT))
            if len(calls) == 1:
                return {"title": "عنوان فقط"}
            return {
                "title": "عنوان صالح",
                "body": "متن صالح",
                "takeaway": "خلاصة صالحة",
                "caption": "تعليق صالح",
                "sources": ["واس", "Reuters"],
                "image_queries": ["Saudi Riyadh street", "Saudi Riyadh people", "Saudi Riyadh city"],
                "image_queries_ar": ["الرياض", "ناس", "مدينة"],
                "image_prompt": "a street scene in Riyadh Saudi Arabia",
                "source_url": "https://example.com/source",
            }

        brief = research_with_validation(bot, original, "موضوع")
        self.assertEqual(brief["title"], "عنوان صالح")
        self.assertEqual(len(calls), 2)
        self.assertIn("فشلت في بوابة الجودة", calls[1][1])
        self.assertEqual(bot.SYSTEM_PROMPT, "base prompt")

    def test_research_retry_prompt_gives_length_target_and_current_count(self):
        calls = []
        bot = SimpleNamespace(SYSTEM_PROMPT="base prompt")
        long_body = "هذه جملة خبرية تشرح الموضوع بوضوح وتضع المعلومة في سياقها من دون أي نصيحة أو توجيه. " * 5

        def original(topic):
            calls.append(bot.SYSTEM_PROMPT)
            brief = {
                "title": "عنوان واضح ومباشر",
                "body": long_body if len(calls) == 1 else "هذه خلاصة خبرية قصيرة تشرح الموضوع بوضوح.",
                "takeaway": "الدلالة الأساسية خبرية وليست توجيهاً للمتابع.",
                "caption": "زاوية مختصرة تشرح لماذا يستحق الموضوع الانتباه.",
                "sources": ["واس", "Reuters"],
                "image_queries": ["Saudi economy Riyadh", "Saudi business Riyadh", "Saudi finance Riyadh"],
                "image_queries_ar": ["اقتصاد سعودي", "أعمال السعودية", "مالية السعودية"],
                "image_prompt": "high-quality editorial photograph about the Saudi economy",
                "source_url": "https://example.com/source",
            }
            return brief

        brief = research_with_validation(bot, original, "موضوع اقتصادي")
        self.assertLessEqual(len(brief["body"]), 260)
        self.assertEqual(len(calls), 2)
        self.assertIn(f"body طوله الحالي {len(long_body.strip())}", calls[1])
        self.assertIn("استهدف 230 حرفاً أو أقل", calls[1])
        self.assertIn("الحد الأقصى 260", calls[1])

    def test_research_compacts_length_only_second_draft_instead_of_failing(self):
        calls = []
        bot = SimpleNamespace(SYSTEM_PROMPT="base prompt")
        long_body = (
            "المعلومة الأساسية واضحة ومهمة للمتابع، وتفاصيلها تشرح السياق الحالي بصورة خبرية دقيقة من دون نصيحة أو توجيه. "
            "كما أن الخلفية تضيف معنى مفيداً لفهم التطور وما الذي تغير ولماذا أصبح الموضوع مهماً الآن. "
            "وتبقى الخلاصة أن الموضوع يستحق الانتباه بسبب أثره المباشر في المشهد المحلي الحالي."
        )
        self.assertGreater(len(long_body), 260)

        def original(topic):
            calls.append(bot.SYSTEM_PROMPT)
            return {
                "title": "عنوان واضح ومباشر",
                "body": long_body,
                "takeaway": "الدلالة الأساسية خبرية وليست توجيهاً للمتابع.",
                "caption": "زاوية مختصرة تشرح لماذا يستحق الموضوع الانتباه.",
                "sources": ["واس", "Reuters"],
                "image_queries": ["Saudi economy Riyadh", "Saudi business Riyadh", "Saudi finance Riyadh"],
                "image_queries_ar": ["اقتصاد سعودي", "أعمال السعودية", "مالية السعودية"],
                "image_prompt": "high-quality editorial photograph about the Saudi economy",
                "source_url": "https://example.com/source",
            }

        brief = research_with_validation(bot, original, "موضوع اقتصادي")
        self.assertEqual(len(calls), 2)
        self.assertLessEqual(len(brief["body"]), 240)
        self.assertFalse(brief["body"].endswith(" "))
        self.assertEqual(topic_snapchat.validate_brief(brief), [])

    def test_research_validation_blocks_after_second_invalid_result(self):
        bot = SimpleNamespace(SYSTEM_PROMPT="base prompt")
        with self.assertRaisesRegex(SystemExit, "failed editorial validation"):
            research_with_validation(bot, lambda topic: {"title": "ناقص"}, "موضوع")

    def test_research_remembers_full_topic_context_for_image_relevance(self):
        remember_story_contexts({"stories": []})
        brief = {
            "title": "العنوان الذي سيراه المتابع",
            "body": "المعلومة الأساسية التي يجب أن تعكسها الصورة",
            "takeaway": "الخلاصة الخبرية",
            "caption": "تعليق",
            "sources": ["واس", "Reuters"],
            "image_queries": ["Saudi Riyadh school", "Saudi students Riyadh", "Saudi classroom"],
            "image_queries_ar": ["الرياض", "طلاب", "مدارس"],
            "image_prompt": "Saudi students in a Riyadh classroom",
            "source_url": "https://example.com/source",
        }
        bot = SimpleNamespace(SYSTEM_PROMPT="base prompt")
        result = research_with_validation(bot, lambda topic: dict(brief), "موضوع")
        story = _story_for_queries(result["image_queries"], result["image_queries_ar"])
        self.assertIsNotNone(story)
        self.assertEqual(story["headline"], brief["title"])
        self.assertEqual(story["summary"], brief["body"])
        self.assertEqual(story["takeaway"], brief["takeaway"])
        self.assertEqual(story["link"], brief["source_url"])
        remember_story_contexts({"stories": []})

    def test_topic_image_story_preserves_exact_recovery_visual(self):
        brief = {
            "title": "لماذا تراجعت الأسهم اليابانية؟",
            "body": "تراجع مؤشر نيكي قبل اجتماع بنك اليابان.",
            "takeaway": "السوق يواجه طاقة أغلى وتمويلاً أعلى كلفة.",
            "source_url": "https://example.com/source",
            "image_queries": ["Bank of Japan", "Nikkei", "Tokyo Stock Exchange"],
            "image_queries_ar": ["بنك اليابان", "نيكي", "بورصة طوكيو"],
            "recovery_image_b64_path": "assets/recovery/bank-of-japan.jpg.b64",
            "recovery_photo_credit": "Verified photographer / license",
            "recovery_visual_kind": "organization_logo",
            "official_image_url": "https://www.aramco.com/-/jssmedia/project/aramcocom/aramco-logo.webp",
        }

        story = topic_snapchat.topic_image_story(brief)

        self.assertEqual(
            story["recovery_image_b64_path"],
            brief["recovery_image_b64_path"],
        )
        self.assertEqual(
            story["recovery_photo_credit"],
            brief["recovery_photo_credit"],
        )
        self.assertEqual(
            story["recovery_visual_kind"],
            brief["recovery_visual_kind"],
        )
        self.assertEqual(
            story["official_image_url"],
            brief["official_image_url"],
        )

    def test_run_74_teacher_like_action_line_is_publish_blocking(self):
        brief = {
            "title": "وش يعني ثبات الفائدة للتمويل المتغير؟",
            "body": "الفائدة المرجعية والتمويل المتغير لا يتحركان دائماً بالطريقة نفسها؛ العقد يحدد المؤشر والهامش وموعد إعادة التسعير.",
            "takeaway": "راجع مؤشر تمويلك المتغير في العقد، ولا تفترض ارتباطه المباشر بقرار واحد.",
            "caption": "ثبات الفائدة لا يعني أن كل تمويل متغير سيبقى كما هو.",
            "sources": ["Federal Reserve", "البنك المركزي السعودي"],
            "image_queries": ["Saudi Central Bank headquarters Riyadh", "Saudi banking finance Riyadh", "Saudi mortgage banking Riyadh"],
            "image_queries_ar": ["البنك المركزي السعودي", "تمويل بنكي", "تمويل عقاري"],
            "image_prompt": "high-quality editorial photograph about Saudi banking and variable-rate financing",
            "source_url": "https://www.sama.gov.sa/",
        }
        errors = topic_snapchat.validate_brief(brief)
        self.assertTrue(any("instructional or advisory" in error for error in errors), errors)

    def test_run_74_institution_comparison_is_publish_blocking(self):
        brief = {
            "title": "الفائدة الأمريكية ثابتة",
            "body": "التمويل المتغير يعتمد على المؤشر المرجعي وهامش البنك وموعد إعادة التسعير.",
            "takeaway": "تكلفة التمويل تتأثر بعدة عوامل، وليس بقرار واحد فقط.",
            "caption": "الفيدرالي ثابت وساما مثله، لكن تفاصيل العقد هي التي تحدد إعادة التسعير.",
            "sources": ["Federal Reserve", "البنك المركزي السعودي"],
            "image_queries": ["Saudi Central Bank headquarters Riyadh", "Saudi banking finance Riyadh", "Saudi mortgage banking Riyadh"],
            "image_queries_ar": ["البنك المركزي السعودي", "تمويل بنكي", "تمويل عقاري"],
            "image_prompt": "high-quality editorial photograph about Saudi banking and variable-rate financing",
            "source_url": "https://www.sama.gov.sa/",
        }
        errors = topic_snapchat.validate_brief(brief)
        self.assertTrue(any("state each institution's decision separately" in error for error in errors), errors)

    def test_verified_ministry_finance_photo_is_direct_for_tax_topic(self):
        photo = Path("ministry-of-finance.jpg")
        context = (
            "حصيلة ضريبة القيمة المضافة: أين تذهب؟ "
            "بلغت الضرائب على السلع والخدمات 288.8 مليار ريال بحسب وزارة المالية."
        )
        with patch.object(
            topic_snapchat,
            "_local_provenance_name",
            return_value="ministry-of-finance",
        ):
            judge = topic_snapchat._direct_relevance_only(
                lambda candidate, story: "neutral"
            )
            self.assertEqual(judge(photo, context), "yes")

    def test_credit_policy_rejects_attribution_required_open_images(self):
        policy = getattr(topic_snapchat, "_credit_requires_visible", None)
        self.assertIsNotNone(policy)
        self.assertTrue(policy("openverse", "Alice / CC BY 4.0"))
        self.assertTrue(policy("commons", "Alice / Wikimedia Commons"))
        self.assertFalse(policy("openverse", "Openverse / CC CC0 1.0"))
        self.assertFalse(policy("openverse", "Public Domain / PDM"))
        self.assertFalse(policy("loc", "Library of Congress"))
        self.assertFalse(policy("stock", "Pexels"))

    def test_install_uses_full_cooldown_snapchat_brand_shared_model_and_auto_images(self):
        rendered_credits = []
        generated_calls = []

        def renderer(brief, out_path, photo_path=None, photo_credit=None):
            rendered_credits.append(photo_credit)
            return out_path

        def pair(*args, **kwargs):
            return None, None

        def stock(*args, **kwargs):
            return None

        def generated(prompt, out_path):
            generated_calls.append((prompt, out_path))
            return Path(out_path), "AI generated"

        bot = SimpleNamespace(
            COOLDOWN_DAYS=21,
            HARD_COOLDOWN_DAYS=5,
            KICKER="ملخص تنفيذي",
            CLAUDE_MODEL="claude-sonnet-5",
            TOPIC_MODEL="claude-opus-5",
            IMAGE_SOURCE="spa",
            SYSTEM_PROMPT="قواعد اللهجة والمصطلح — اكتب بلسان سعودي رسمي:\n",
            SELECT_PROMPT="اختر الموضوع",
            research=lambda topic: {},
            TOPICS_FILE=Path("topics.txt"),
            choose_topic=lambda exclude=(): "قديم",
            render_story=renderer,
            render_topic=renderer,
            fetch_local_photo=pair,
            fetch_article_photo=pair,
            fetch_spa_photo=pair,
            fetch_commons_photo=pair,
            fetch_loc_photo=pair,
            fetch_openverse_photo=pair,
            fetch_photo=stock,
            fetch_generated_photo=generated,
            photo_shows=lambda photo, context: "neutral",
            recent_fallback=lambda path: "old-unrelated-photo.jpg",
            _AUTO_IMAGE_SELECTOR_INSTALLED=False,
        )
        with patch.dict("os.environ", {"ALLOW_GENERATED": "0"}, clear=False):
            install(bot)
        self.assertEqual(bot.HARD_COOLDOWN_DAYS, 21)
        self.assertEqual(bot.KICKER, "معلومة تهمك")
        self.assertEqual(bot.TOPIC_MODEL, bot.CLAUDE_MODEL)
        self.assertEqual(bot.IMAGE_SOURCE, "auto")
        self.assertTrue(bot._AUTO_IMAGE_SELECTOR_INSTALLED)
        self.assertNotIn("بلسان سعودي رسمي", bot.SYSTEM_PROMPT)
        self.assertIn("سناب شات", bot.SELECT_PROMPT)

        # Topic Brief is stricter than Daily News: neutral imagery, unrelated
        # recent-photo reuse, and generated imagery are not valid fallbacks.
        self.assertEqual(bot.photo_shows(Path("candidate.jpg"), "topic"), "no")
        self.assertIsNone(bot.recent_fallback(Path("hero.jpg")))
        self.assertEqual(
            bot.fetch_generated_photo("topic prompt", Path("hero.jpg")),
            (None, None),
        )
        self.assertEqual(generated_calls, [])

        # The bot surfaces what matters; it does not tell the follower what to do.
        self.assertIn("ليس دورك أن تعلّم", bot.SYSTEM_PROMPT)
        self.assertIn("takeaway", bot.SYSTEM_PROMPT)
        self.assertIn("صورة تحريرية عالية الجودة", bot.SYSTEM_PROMPT)
        self.assertNotIn("يمكن للمتابع استخدامه", bot.SELECT_PROMPT)

        bot.render_story({}, Path("card.png"), Path("hero.jpg"), "Pexels")
        bot.render_topic({}, Path("card.png"), Path("hero.jpg"), "SPA")
        self.assertEqual(rendered_credits, [None, None])

    def test_topic_workflow_has_no_image_source_choice_and_forces_auto(self):
        workflow = Path(".github/workflows/topic.yml").read_text(encoding="utf-8")
        self.assertNotIn("image_source:", workflow)
        self.assertNotIn("inputs.image_source", workflow)
        self.assertIn('IMAGE_SOURCE: "auto"', workflow)


if __name__ == "__main__":
    unittest.main()
