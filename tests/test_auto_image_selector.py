import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

import daily_news_fresh_runner
import daily_news_runner


class AutoImageSourcePolicyTests(unittest.TestCase):
    def test_news_judge_uses_news_context_without_changing_shared_story_prompt(self):
        news = SimpleNamespace(_VISION_JUDGE="historical frame policy")
        story = SimpleNamespace(_VISION_JUDGE="historical frame policy")
        daily_news_fresh_runner.install_news_visual_quality_guidance(news)
        self.assertIn("لا يلزم أن توثق الصورة", news._VISION_JUDGE)
        self.assertIn("جهة أو شخص آخر", news._VISION_JUDGE)
        self.assertIn("{context}", news._VISION_JUDGE)
        self.assertEqual(story._VISION_JUDGE, "historical frame policy")
        self.assertNotIn("historical frame policy", news._VISION_JUDGE)

    def test_normalize_image_source_defaults_and_aliases(self):
        self.assertEqual(daily_news_runner.normalize_image_source(None), "auto")
        self.assertEqual(daily_news_runner.normalize_image_source(""), "auto")
        self.assertEqual(daily_news_runner.normalize_image_source("spa"), "spa")
        self.assertEqual(daily_news_runner.normalize_image_source("pexels"), "stock")
        self.assertEqual(daily_news_runner.normalize_image_source("bogus"), "auto")

    def make_module(self):
        def noop_pair(*args, **kwargs):
            return None, None

        def noop_photo(*args, **kwargs):
            return None

        return SimpleNamespace(
            LOOKBACK_HOURS=30,
            SYSTEM_PROMPT="old",
            MAX_HEADLINES_TO_MODEL=60,
            summarize=lambda items, already_posted=(), pinned="": {"stories": []},
            _http_get=lambda _: b"<rss><channel></channel></rss>",
            _clean=lambda x: x or "",
            _parse_date=lambda x: None,
            IMAGE_SOURCE="spa",
            PEXELS_API_KEY="key",
            DOMAIN_CREDITS={"aawsat.com": "الشرق الأوسط"},
            photo_shows=lambda path, context: "yes",
            fetch_local_photo=noop_pair,
            fetch_article_photo=noop_pair,
            fetch_spa_photo=noop_pair,
            fetch_commons_photo=noop_pair,
            fetch_loc_photo=noop_pair,
            fetch_openverse_photo=noop_pair,
            fetch_photo=noop_photo,
        )

    def test_configure_defaults_to_auto_and_installs_wrappers(self):
        fake = self.make_module()
        original_local = fake.fetch_local_photo
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IMAGE_SOURCE", None)
            os.environ.pop("LOOKBACK_HOURS", None)
            daily_news_runner.configure(fake)
        self.assertEqual(fake.IMAGE_SOURCE, "auto")
        self.assertIsNot(fake.fetch_local_photo, original_local)

    def test_manual_override_preserves_legacy_provider_functions(self):
        fake = self.make_module()
        original_local = fake.fetch_local_photo
        with patch.dict(os.environ, {"IMAGE_SOURCE": "commons"}, clear=False):
            daily_news_runner.configure(fake)
        self.assertEqual(fake.IMAGE_SOURCE, "commons")
        self.assertIs(fake.fetch_local_photo, original_local)


class RelevanceFirstWrapperTests(unittest.TestCase):
    def make_module(self, verdicts, calls, *, local_marker=False, pexels_key="key",
                    commons_title="File:Apple iPhone launch.jpg"):
        def write(path, label, marker=False):
            Path(path).write_bytes(label.encode("utf-8"))
            if marker:
                Path(str(path) + ".exempt").write_text(
                    f"local:{label}.jpg", encoding="utf-8")
            return str(path)

        def local(queries_ar, queries_en, out_path,
                  respect_cooldown=True, exclude=()):
            calls.append("local")
            return write(out_path, "local", local_marker), "Local credit"

        def article(url, out_path):
            calls.append("article")
            return write(out_path, "article"), "aawsat.com"

        def spa(queries_ar, out_path):
            calls.append("spa")
            return write(out_path, "spa"), "واس"

        def commons(queries, out_path, need_saudi=None, min_hits=None,
                    subject_mode=False):
            calls.append("commons")
            photo = write(out_path, "commons")
            Path(str(out_path) + ".commons-title").write_text(
                commons_title, encoding="utf-8")
            return photo, "Commons credit"

        def loc(queries, out_path, need_saudi=None, min_hits=None,
                subject_mode=False):
            calls.append("loc")
            return write(out_path, "loc"), "Library of Congress"

        def openverse(queries, out_path, need_saudi=None, min_hits=None,
                      subject_mode=False):
            calls.append("openverse")
            return write(out_path, "openverse"), "Openverse credit"

        def stock(queries, out_path, need_saudi=None):
            calls.append("stock")
            return write(out_path, "stock")

        def judge(path, context):
            label = Path(path).read_bytes().decode("utf-8")
            return verdicts[label]

        return SimpleNamespace(
            IMAGE_SOURCE="auto",
            PEXELS_API_KEY=pexels_key,
            DOMAIN_CREDITS={"aawsat.com": "الشرق الأوسط"},
            photo_shows=judge,
            fetch_local_photo=local,
            fetch_article_photo=article,
            fetch_spa_photo=spa,
            fetch_commons_photo=commons,
            fetch_loc_photo=loc,
            fetch_openverse_photo=openverse,
            fetch_photo=stock,
        )

    def remember_story(self, *, scope="saudi"):
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "Apple تغيّر شيئاً مهماً في iPhone",
                "summary": "التغيير يصل للمستخدمين في السعودية.",
                "takeaway": "قد يؤثر على قرار الشراء القادم.",
                "link": "https://aawsat.com/story",
                "scope": scope,
                "image_queries": ["apple iphone saudi arabia"],
                "image_queries_ar": ["آيفون"],
            }]
        })

    def run_auto(self, fake, hero):
        daily_news_runner.install_auto_image_selector(fake)
        return fake.fetch_local_photo(
            ["آيفون"], ["apple iphone saudi arabia"], hero)

    def test_explicit_exact_organization_logo_bypasses_generic_graphic_gate(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "no",
            "commons": "no", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls)
        fake.looks_like_a_graphic = lambda path: True
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "دراسة كاوست عن الغذاء العالمي",
                "summary": "دراسة تقودها كاوست عن اللافقاريات المائية.",
                "takeaway": "مصدر غذائي بديل.",
                "link": "https://www.alyaum.com/articles/6681982",
                "scope": "saudi",
                "image_queries": ["apple iphone saudi arabia"],
                "image_queries_ar": ["آيفون"],
                "visual_targets": [{
                    "kind": "organization",
                    "name_en": "KAUST",
                    "name_ar": "كاوست",
                }],
                "recovery_visual_kind": "organization_logo",
                "recovery_image_b64_path": (
                    "assets/recovery/kaust-official-logo.png.b64"
                ),
                "recovery_photo_credit": "KAUST",
            }]
        })

        def exact_visual(story, out_path):
            Image.new("RGB", (1200, 300), (0, 0, 0)).save(
                out_path, "JPEG", quality=95
            )
            Path(str(out_path) + ".official-subject").write_text(
                "asset:kaust-logo", encoding="utf-8"
            )
            return str(out_path), "KAUST"

        with tempfile.TemporaryDirectory() as td, patch(
            "daily_news_runner.fetch_verified_official_visual",
            side_effect=exact_visual,
        ):
            photo, credit = self.run_auto(fake, Path(td) / "hero.jpg")
            with Image.open(photo) as rendered:
                self.assertEqual(rendered.size, (1280, 960))
                self.assertTrue(all(channel > 230 for channel in
                                    rendered.getpixel((10, 10))))
                self.assertTrue(all(channel < 20 for channel in
                                    rendered.getpixel((640, 480))))
            self.assertEqual(credit, "KAUST")

    def test_news_never_promotes_uncertain_device_from_filename(self):
        fake = self.make_module(dict.fromkeys(
            ["local", "article", "spa", "commons", "loc", "openverse", "stock"],
            "neutral"), [], commons_title="File:Apple iPhone launch.jpg")
        daily_news_fresh_runner.install_news_visual_quality_guidance(fake)
        self.remember_story()
        with tempfile.TemporaryDirectory() as td:
            photo, credit = self.run_auto(fake, Path(td) / "hero.jpg")
            self.assertIsNone(photo)
            self.assertIsNone(credit)

    def test_news_uses_metadata_screened_openverse_neutral_before_dead_run(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "no",
            "commons": "no", "loc": "no", "openverse": "neutral",
            "stock": "no",
        }, calls)
        daily_news_fresh_runner.install_news_visual_quality_guidance(fake)
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "قراصنة يستنزفون رصيد اشتراكات مستخدمي Claude",
                "summary": "استغل مهاجمون حسابات Claude لاستهلاك الرصيد.",
                "takeaway": "المستخدم قد يكتشف استنزاف رصيده دون علمه.",
                "link": "https://techcrunch.com/claude-credits",
                "scope": "world",
                "image_queries": ["Anthropic Claude AI"],
                "image_queries_ar": ["أنثروبيك كلود"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["أنثروبيك كلود"], ["Anthropic Claude AI"], hero,
            )

            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "Openverse credit")
            self.assertEqual(hero.read_bytes(), b"openverse")

    def test_named_person_recovers_with_strict_commons_portrait(self):
        calls = []
        fake = self.make_module({name: "no" for name in (
            "local", "article", "spa", "commons", "loc", "openverse", "stock"
        )}, calls)

        def portrait(name, out_path):
            calls.append(f"portrait:{name}")
            Path(out_path).write_bytes(b"portrait")
            return str(out_path), "Portrait credit"

        fake.fetch_commons_portrait = portrait
        daily_news_runner.remember_story_contexts({"stories": [{
            "headline": "شخصية عامة تعلن قراراً",
            "summary": "قرار جديد.",
            "takeaway": "القرار يهم المتابع.",
            "link": "https://example.com/person",
            "scope": "world",
            "image_queries": ["Satya Nadella"],
            "image_queries_ar": ["ساتيا ناديلا"],
            "visual_targets": [{
                "kind": "person", "name_en": "Satya Nadella",
                "name_ar": "ساتيا ناديلا",
            }],
        }]})
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["ساتيا ناديلا"], ["Satya Nadella"], hero
            )

            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "Portrait credit")
            self.assertEqual(hero.read_bytes(), b"portrait")
        self.assertIn("portrait:Satya Nadella", calls)

    def test_named_organization_recovers_with_exact_current_logo(self):
        calls = []
        fake = self.make_module({name: "no" for name in (
            "local", "article", "spa", "commons", "loc", "openverse", "stock"
        )}, calls)
        daily_news_runner.remember_story_contexts({"stories": [{
            "headline": "OpenAI تعلن تحديثاً مهماً",
            "summary": "التحديث يصل إلى المستخدمين.",
            "takeaway": "قد يتغير استخدام الخدمة.",
            "link": "https://example.com/openai",
            "scope": "world",
            "image_queries": ["OpenAI"],
            "image_queries_ar": ["أوبن أي آي"],
            "visual_targets": [{
                "kind": "organization", "name_en": "OpenAI", "name_ar": ""
            }],
        }]})
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["أوبن أي آي"], ["OpenAI"], hero
            )

            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "OpenAI")
            self.assertTrue(Path(str(hero) + ".exempt").exists())
            with Image.open(hero) as rendered:
                self.assertEqual(rendered.mode, "RGB")
                self.assertTrue(all(channel > 230 for channel in rendered.getpixel((5, 5))))

    def test_visual_targets_expand_every_live_provider_search(self):
        calls = []
        seen_queries = []
        fake = self.make_module({name: "no" for name in (
            "local", "article", "spa", "commons", "loc", "openverse", "stock"
        )}, calls)

        def commons(queries, out_path, need_saudi=None):
            seen_queries.extend(queries)
            return None, None

        fake.fetch_commons_photo = commons
        daily_news_runner.remember_story_contexts({"stories": [{
            "headline": "شركة تعلن تحديثاً",
            "summary": "تحديث لخدمة رقمية.",
            "takeaway": "قد يتغير استخدام الخدمة.",
            "link": "https://example.com/update",
            "scope": "world",
            "image_queries": ["hard event query"],
            "image_queries_ar": ["حدث صعب"],
            "visual_targets": [
                {"kind": "organization", "name_en": "OpenAI", "name_ar": ""},
                {"kind": "context", "name_en": "AI research", "name_ar": "أبحاث الذكاء الاصطناعي"},
            ],
        }]})
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            fake.fetch_local_photo(
                ["حدث صعب"], ["hard event query"], Path(td) / "hero.jpg"
            )

        self.assertIn("OpenAI", seen_queries)
        self.assertIn("AI research", seen_queries)

    def test_news_rejects_older_model_photo_for_numbered_product_launch(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "no",
            "commons": "yes", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls, commons_title="File:Mi MIX Fold back.jpg")
        daily_news_fresh_runner.install_news_visual_quality_guidance(fake)
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "Xiaomi تكشف هاتفها 18 Fold القابل للطي",
                "summary": "عرضت Xiaomi هاتف 18 Fold قبل إطلاقه.",
                "takeaway": "المنافسة على الهواتف القابلة للطي تتصاعد.",
                "link": "https://engadget.com/xiaomi-18-fold",
                "scope": "world",
                "image_queries": ["Xiaomi 18 Fold IFA 2026"],
                "image_queries_ar": ["هاتف شاومي 18 فولد"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            photo, credit = fake.fetch_local_photo(
                ["هاتف شاومي 18 فولد"],
                ["Xiaomi 18 Fold IFA 2026"],
                Path(td) / "hero.jpg",
            )

        self.assertIsNone(photo)
        self.assertIsNone(credit)

    def test_news_allows_institutional_context_for_numbered_product_launch(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "no",
            "commons": "yes", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls, commons_title="File:Apple Park aerial view.jpg")
        daily_news_fresh_runner.install_news_visual_quality_guidance(fake)
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "Apple تستعد للكشف عن iPhone 17",
                "summary": "تعقد Apple حدثها في مقرها Apple Park.",
                "takeaway": "الأنظار تتجه إلى أحدث هواتف الشركة.",
                "link": "https://example.com/apple-event",
                "scope": "world",
                "image_queries": ["Apple iPhone 17 event Apple Park"],
                "image_queries_ar": ["حدث أبل آيفون 17"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            photo, credit = fake.fetch_local_photo(
                ["حدث أبل آيفون 17"],
                ["Apple iPhone 17 event Apple Park"],
                Path(td) / "hero.jpg",
            )

        self.assertIsNotNone(photo)
        self.assertEqual(credit, "Commons credit")

    def test_later_yes_beats_earlier_neutral_in_one_auto_search(self):
        calls = []
        fake = self.make_module({
            "local": "neutral", "article": "yes", "spa": "no",
            "commons": "no", "loc": "no", "openverse": "no", "stock": "no",
        }, calls)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "الشرق الأوسط")
            self.assertEqual(hero.read_bytes(), b"article")

        self.assertEqual(calls, ["local", "article"])

    def test_visual_judge_receives_photo_provenance(self):
        calls = []
        seen_contexts = []
        fake = self.make_module({
            "local": "yes", "article": "no", "spa": "no",
            "commons": "no", "loc": "no", "openverse": "no", "stock": "no",
        }, calls)

        def judge(path, context):
            seen_contexts.append(context)
            return "yes"

        fake.photo_shows = judge
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            self.run_auto(fake, Path(td) / "hero.jpg")

        self.assertIn("Local credit", seen_contexts[0])

    def test_curated_commons_neutral_is_used_when_no_direct_photo_exists(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "neutral",
            "commons": "neutral", "loc": "no", "openverse": "neutral",
            "stock": "no",
        }, calls)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "Commons credit")
            self.assertEqual(hero.read_bytes(), b"commons")

        self.assertEqual(
            calls, ["local", "article", "spa", "commons", "loc", "openverse", "stock"])

    def test_unrelated_commons_title_blocks_neutral_fallback(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls, commons_title="File:Perth CBD 200520 gnangarra-138.jpg")
        self.remember_story(scope="world")

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)

    def test_neutral_commons_rejects_generic_store_for_named_retailer(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "neutral", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls, commons_title=(
            "File:Convenience Store on High Street, Ingatestone.jpg"
        ))
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "Next تفوز بإلغاء حكم مساواة أجور",
                "summary": "قضت محكمة بأن Next يمكنها دفع أجور مختلفة.",
                "takeaway": "الحكم يخص متاجر Next وعمال المستودعات.",
                "link": "https://bbc.co.uk/news/next-equal-pay",
                "scope": "world",
                "image_queries": [
                    "Next retailer UK store",
                    "UK high street store",
                ],
                "image_queries_ar": ["شركة Next البريطانية"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["شركة Next البريطانية"],
                ["Next retailer UK store", "UK high street store"],
                hero,
            )

        self.assertIsNone(photo)
        self.assertIsNone(credit)

    def test_neutral_commons_rejects_generic_gulf_view_for_khafji(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "neutral", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls, commons_title="File:Colours of the Persian Gulf.jpg")
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "صندوق الاستثمارات يطلق شركة لتطوير ساحل الخفجي",
                "summary": "شركة جديدة لتطوير وجهة سياحية وسكنية في الخفجي.",
                "takeaway": "المشروع يستهدف ساحل الخفجي.",
                "link": "https://alwatan.com.sa/article/1185242",
                "scope": "saudi",
                "image_queries": [
                    "Khafji coast Saudi Arabia",
                    "eastern province gulf coast",
                ],
                "image_queries_ar": ["ساحل الخفجي"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["ساحل الخفجي"],
                ["Khafji coast Saudi Arabia", "eastern province gulf coast"],
                hero,
            )

        self.assertIsNone(photo)
        self.assertIsNone(credit)

    def test_neutral_commons_rejects_wrong_ministry_despite_riyadh_match(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "neutral", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls, commons_title=(
            "File:Ministry of Education, Riyadh, Saudi Arabia.JPG"
        ))
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "قرار جديد يربط نقل ملكية الأراضي البيضاء بسداد الرسوم",
                "summary": "يشترط القرار سداد رسوم الأراضي البيضاء قبل التوثيق.",
                "takeaway": "السداد أصبح شرطاً لنقل الملكية.",
                "link": "https://alyaum.com/white-land-fees",
                "scope": "saudi",
                "image_queries": [
                    "Saudi white land fees property transfer",
                    "Riyadh government building",
                ],
                "image_queries_ar": ["رسوم الأراضي البيضاء"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["رسوم الأراضي البيضاء"],
                ["Saudi white land fees property transfer", "Riyadh government building"],
                hero,
            )

        self.assertIsNone(photo)
        self.assertIsNone(credit)

    def test_neutral_commons_rejects_empty_stadium_for_player_transfer(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls, commons_title="File:Jawhara Stadium Jeddah.jpg")
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "ديابي يقترب من الأهلي باتفاق حتى 2029",
                "summary": "اقترب النادي الأهلي من ضم موسى ديابي.",
                "takeaway": "الصفقة تدعم هجوم الأهلي بلاعب دولي.",
                "link": "https://akhbaar24.com/diaby-al-ahli",
                "scope": "saudi",
                "image_queries": [
                    "Moussa Diaby Al Ahli transfer",
                    "Jeddah football stadium",
                ],
                "image_queries_ar": ["موسى ديابي الأهلي"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["موسى ديابي الأهلي"],
                ["Moussa Diaby Al Ahli transfer", "Jeddah football stadium"],
                hero,
            )

        self.assertIsNone(photo)
        self.assertIsNone(credit)

    def test_neutral_commons_rejects_generic_refinery_for_oil_price_story(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls, commons_title="File:Saudi Arabia oil refinery.jpg")
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "أسعار النفط تتجاوز 96 دولاراً مع توتر في هرمز",
                "summary": "واصل النفط ارتفاعه مع مخاوف من اضطراب الإمدادات.",
                "takeaway": "ارتفاع النفط يعني عادة إيرادات أعلى للمصدرين.",
                "link": "https://aawsat.com/node/5315462",
                "scope": "saudi",
                "image_queries": ["saudi arabia oil refinery"],
                "image_queries_ar": ["أسعار النفط مضيق هرمز"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["أسعار النفط مضيق هرمز"],
                ["saudi arabia oil refinery"],
                hero,
            )

        self.assertIsNone(photo)
        self.assertIsNone(credit)

    def test_neutral_commons_rejects_unmentioned_archival_year(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls, commons_title="File:A view of the Bahrein Refinery, 1949.jpg")
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "أسعار النفط تتجاوز 96 دولاراً مع توتر في هرمز",
                "summary": "واصل النفط ارتفاعه مع مخاوف من اضطراب الإمدادات.",
                "takeaway": "ارتفاع النفط يعني عادة إيرادات أعلى للمصدرين.",
                "link": "https://aawsat.com/node/5315462",
                "scope": "saudi",
                "image_queries": ["Bahrein oil refinery"],
                "image_queries_ar": ["أسعار النفط مضيق هرمز"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["أسعار النفط مضيق هرمز"],
                ["Bahrein oil refinery"],
                hero,
            )

        self.assertIsNone(photo)
        self.assertIsNone(credit)

    def test_neutral_named_subject_photo_is_not_archival_only_due_to_2009_date(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls, commons_title=(
            "File:Flynas A320-214, VP-CXP, MSN 3889 (05 2009), "
            "as XY 72 Riyadh.jpg"
        ))
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "طيران ناس تستحوذ على حصة في سويسبورت السعودية",
                "summary": "أعلنت طيران ناس استحواذها على حصة في الشركة.",
                "takeaway": "الصفقة توسع حضور الناقلة في خدمات المطارات.",
                "link": "https://aawsat.com/flynas-swissport",
                "scope": "saudi",
                "image_queries": ["flynas aircraft Riyadh airport"],
                "image_queries_ar": ["طيران ناس"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["طيران ناس"], ["flynas aircraft Riyadh airport"], hero,
            )

        self.assertEqual(str(hero), photo)
        self.assertEqual("Commons credit", credit)

    def test_neutral_financial_district_photo_is_too_generic_for_sukuk(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "neutral", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "neutral",
            "stock": "no",
        }, calls, commons_title="File:Financial District Riyadh 2012.jpg")
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "اكتتاب في صكوك صح بعائد 4.8% حتى 8 سبتمبر",
                "summary": "فتح المركز الوطني لإدارة الدين الاكتتاب في صكوك صح.",
                "takeaway": "الصكوك أداة ادخار حكومية بعائد ثابت.",
                "link": "https://alyaum.com/sah-sukuk",
                "scope": "saudi",
                "image_queries": [
                    "riyadh financial district",
                    "saudi national debt office",
                ],
                "image_queries_ar": ["صكوك صح", "المركز الوطني لإدارة الدين"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = fake.fetch_local_photo(
                ["صكوك صح", "المركز الوطني لإدارة الدين"],
                ["riyadh financial district", "saudi national debt office"],
                hero,
            )

        self.assertIsNone(photo)
        self.assertIsNone(credit)

    def test_verified_official_visual_download_is_allowlisted(self):
        source = io.BytesIO()
        Image.new("RGBA", (120, 80), (0, 0, 0, 0)).save(
            source, format="PNG", compress_level=0
        )
        image_data = source.getvalue()

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit=-1):
                return image_data

        story = {
            "official_image_url": (
                "https://sukuk.ndmc.gov.sa/image/layout_set_logo"
                "?img_id=155814&t=1779205254815"
            )
        }
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "official.jpg"
            photo, credit = daily_news_runner.fetch_verified_official_visual(
                story, target, opener=lambda *args, **kwargs: Response()
            )
            self.assertEqual(photo, str(target))
            self.assertIsNone(credit)
            self.assertTrue(Path(str(target) + ".official-subject").exists())
            with Image.open(target) as rendered:
                pixel = rendered.convert("RGB").getpixel((60, 40))
            self.assertTrue(all(channel > 230 for channel in pixel))

    def test_curated_recovery_photo_requires_attribution(self):
        source = io.BytesIO()
        Image.new("RGB", (120, 80), (145, 98, 45)).save(
            source, format="PNG", compress_level=0
        )
        image_data = source.getvalue()

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit=-1):
                return image_data

        story = {
            "recovery_image_url": (
                "https://upload.wikimedia.org/wikipedia/commons/1/1a/"
                "Saudi_coins_%281%29.jpg"
            ),
            "recovery_photo_credit": "Sajetpa / CC BY-SA 3.0",
        }
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "coins.jpg"
            photo, credit = daily_news_runner.fetch_verified_official_visual(
                story, target, opener=lambda *args, **kwargs: Response()
            )
            self.assertEqual(photo, str(target))
            self.assertEqual(credit, "Sajetpa / CC BY-SA 3.0")

    def test_curated_publisher_recovery_photo_is_allowlisted_with_credit(self):
        source = io.BytesIO()
        Image.effect_noise((160, 100), 30).convert("RGB").save(
            source, format="JPEG", quality=92
        )
        image_data = source.getvalue()

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit=-1):
                return image_data

        story = {
            "recovery_image_url": (
                "https://arabic.arabianbusiness.com/cloud/2024/11/03/"
                "9ASXhkUp-12-1024x683.jpg"
            ),
            "recovery_photo_credit": "Arabian Business",
        }
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "sah.jpg"
            photo, credit = daily_news_runner.fetch_verified_official_visual(
                story, target, opener=lambda *args, **kwargs: Response()
            )
            self.assertEqual(photo, str(target))
            self.assertEqual(credit, "Arabian Business")

    def test_news_guidance_rejects_old_coins_for_modern_financial_products(self):
        guidance = daily_news_fresh_runner.NEWS_VISUAL_QUALITY_GUIDANCE
        self.assertIn("العملات القديمة", guidance)
        self.assertIn("أكوام النقود", guidance)
        self.assertIn("قناة الاكتتاب", guidance)

    def test_news_guidance_accepts_literal_commodity_named_in_headline(self):
        guidance = daily_news_fresh_runner.NEWS_VISUAL_QUALITY_GUIDANCE
        self.assertIn("سبائك الذهب", guidance)
        self.assertIn("الذهب نفسه", guidance)
        self.assertIn("ليست عن منتج مالي مسمّى", guidance)

    def test_repository_recovery_asset_is_decoded_with_credit(self):
        story = {
            "recovery_image_b64_path": (
                "assets/recovery/sah-modern-photo.jpg.b64"
            ),
            "recovery_photo_credit": "Arabian Business",
        }
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "sah.jpg"
            photo, credit = daily_news_runner.fetch_verified_official_visual(
                story, target
            )
            self.assertEqual(photo, str(target))
            self.assertEqual(credit, "Arabian Business")
            with Image.open(target) as rendered:
                self.assertEqual(rendered.size, (1024, 683))

    def test_curated_recovery_photo_without_attribution_is_rejected(self):
        story = {
            "recovery_image_url": (
                "https://upload.wikimedia.org/wikipedia/commons/1/1a/"
                "Saudi_coins_%281%29.jpg"
            )
        }
        photo, credit = daily_news_runner.fetch_verified_official_visual(story, "x")
        self.assertIsNone(photo)
        self.assertIsNone(credit)

    def test_neutral_old_coin_photo_is_too_generic_for_sah_sukuk(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "neutral", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "neutral",
            "stock": "no",
        }, calls, commons_title="File:Saudi coins (1).jpg")
        daily_news_runner.remember_story_contexts({
            "stories": [{
                "headline": "اكتتاب في صكوك صح بعائد 4.8% حتى 8 سبتمبر",
                "summary": "فتح المركز الوطني لإدارة الدين الاكتتاب في صكوك صح.",
                "takeaway": "الصكوك أداة ادخار حكومية بعائد ثابت.",
                "link": "https://alyaum.com/sah-sukuk",
                "scope": "saudi",
                "image_queries": ["saudi riyal coins savings"],
                "image_queries_ar": ["صكوك صح"],
            }]
        })
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            photo, credit = fake.fetch_local_photo(
                ["صكوك صح"], ["saudi riyal coins savings"], Path(td) / "hero.jpg"
            )

        self.assertIsNone(photo)
        self.assertIsNone(credit)

    def test_no_candidate_is_never_promoted(self):
        calls = []
        fake = self.make_module({
            name: "no" for name in
            ("local", "article", "spa", "commons", "loc", "openverse", "stock")
        }, calls)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)

    def test_curated_commons_neutral_keeps_provider_credit(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "no",
            "commons": "neutral", "loc": "no", "openverse": "no",
            "stock": "no",
        }, calls)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "Commons credit")
            self.assertEqual(hero.read_bytes(), b"commons")


    def test_local_neutral_is_not_promoted_or_left_exempt(self):
        calls = []
        fake = self.make_module({
            "local": "neutral", "article": "no", "spa": "no",
            "commons": "no", "loc": "no", "openverse": "no", "stock": "no",
        }, calls, local_marker=True)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)
            self.assertFalse(Path(str(hero) + ".exempt").exists())


    def test_rejected_local_marker_does_not_leak_when_article_is_neutral(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "neutral", "spa": "no",
            "commons": "no", "loc": "no", "openverse": "no", "stock": "no",
        }, calls, local_marker=True)
        self.remember_story()

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)
            self.assertFalse(Path(str(hero) + ".exempt").exists())


    def test_world_story_skips_spa_and_uses_neutral_commons(self):
        calls = []
        fake = self.make_module({
            "local": "no", "article": "no", "spa": "yes",
            "commons": "neutral", "loc": "no", "openverse": "no", "stock": "no",
        }, calls)
        self.remember_story(scope="world")

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, credit = self.run_auto(fake, hero)
            self.assertEqual(photo, str(hero))
            self.assertEqual(credit, "Commons credit")
            self.assertEqual(hero.read_bytes(), b"commons")
        self.assertNotIn("spa", calls)


    def test_downstream_legacy_provider_is_suppressed_after_auto_exhaustion(self):
        calls = []
        fake = self.make_module({
            name: "no" for name in
            ("local", "article", "spa", "commons", "loc", "openverse", "stock")
        }, calls)
        self.remember_story()
        daily_news_runner.install_auto_image_selector(fake)

        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / "hero.jpg"
            photo, _ = fake.fetch_local_photo(
                ["آيفون"], ["apple iphone saudi arabia"], hero)
            self.assertIsNone(photo)
            before = list(calls)
            photo, credit = fake.fetch_article_photo("https://aawsat.com/story", hero)
            self.assertIsNone(photo)
            self.assertIsNone(credit)
            self.assertEqual(calls, before)


if __name__ == "__main__":
    unittest.main()
