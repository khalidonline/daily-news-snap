# Saudi Snapchat Editorial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Broaden `daily-news-snap` into a Saudi-interest Snapchat news editor for Arabic-speaking adults aged roughly 25–50 by adding dedicated Saudi-interest feeds, filtering obvious hyperlocal/routine noise, balancing the model shortlist across editorial lanes, and rewriting the selection/copy prompt without changing the public card or publishing contracts.

**Architecture:** Put feed metadata, audience-fit gating, shortlist balancing, and the editorial prompt in a focused `news_editorial.py` module so the 178KB `news_bot.py` stays mostly orchestration. `news_bot.py` will fetch each configured feed with its lane tag, deduplicate as it already does, pass items through a deterministic audience-fit gate and lane-aware shortlist builder, then send that balanced shortlist to the existing Claude call. Rendering, photo selection, breaking-news confirmation, Snapchat publishing, and the JSON output schema remain unchanged.

**Tech Stack:** Python 3.12, standard-library `re`, `collections`, `unittest`, existing `urllib`/XML feed ingestion, Anthropic API integration already present in `news_bot.py`.

**Spec:** `docs/superpowers/specs/2026-08-29-saudi-snapchat-editorial-design.md`

## Global Constraints

- Target audience: primarily Saudi/Arabic-speaking Snapchat users aged roughly 25–50.
- `saudi_core` means broad Saudi relevance, not any story that happens inside Saudi Arabia.
- Hyperlocal municipal/city news must not consume shortlist space merely because it is Saudi.
- Lane allocations are maximum opportunities/initial targets, never minimum quotas; weak lanes may contribute zero and unused capacity flows to stronger qualified stories.
- Initial 60-item shortlist targets: `business_tech` 20, `saudi_core` 16, `sports` 8, `entertainment_culture` 8, `travel_lifestyle` 8.
- Major Saudi sports, entertainment/culture, travel, and lifestyle stories are eligible; gossip, routine scores/fixtures, minor transfers, routine PR, and youth-only chatter remain low priority or rejected.
- Preserve the public JSON schema: `headline`, `summary`, `takeaway`, `source`, `item`, `scope`, `image_queries`, `image_queries_ar`.
- Preserve renderer contracts, photo-selection/vision gates, publishing code, posting frequency, and breaking-news confirmation threshold.
- Normal feed runs may only use facts present in the supplied title/summary; pinned breaking events keep the existing verification/search flow.
- Preserve existing numerical-comparison rules, public-finance neutrality, Latin digits, and company/entity naming rules.
- No additional model call is introduced in Phase 1.

---

## File Structure

- **Create `news_editorial.py`** — owns feed registry/lane metadata, basic audience-fit filtering, lane-aware shortlist construction, lane statistics, and the Saudi 25–50 editorial prompt.
- **Modify `news_bot.py`** — imports the editorial module, fetches lane-tagged feeds, carries `lane` on internal items, uses the balanced shortlist before the Claude call, and logs lane representation.
- **Create `tests/test_news_editorial.py`** — deterministic tests for source configuration, audience-fit filtering, deduplication, lane balancing, spillover, source fairness, and prompt policy.
- **Do not modify** renderer/publishing/breaking modules unless a regression test proves the integration requires it.

---

### Task 1: Create the feed registry and basic Saudi-adult audience gate

**Files:**
- Create: `news_editorial.py`
- Create: `tests/test_news_editorial.py`

**Interfaces:**
- Produces: `FEED_SPECS: tuple[dict[str, str], ...]`
- Produces: `LANE_TARGETS: dict[str, int]`
- Produces: `audience_fit_eligible(item: dict) -> bool`
- Later tasks consume those exact names.

- [ ] **Step 1: Write failing configuration tests**

Create `tests/test_news_editorial.py` with `unittest` and begin with these tests:

```python
import unittest

from news_editorial import FEED_SPECS, LANE_TARGETS, audience_fit_eligible


class NewsEditorialTests(unittest.TestCase):
    def test_lane_targets_cover_sixty_model_slots(self):
        self.assertEqual(
            LANE_TARGETS,
            {
                "business_tech": 20,
                "saudi_core": 16,
                "sports": 8,
                "entertainment_culture": 8,
                "travel_lifestyle": 8,
            },
        )
        self.assertEqual(sum(LANE_TARGETS.values()), 60)

    def test_feed_registry_contains_each_required_saudi_interest_lane(self):
        lanes = {feed["lane"] for feed in FEED_SPECS}
        self.assertTrue({
            "saudi_core",
            "business_tech",
            "sports",
            "entertainment_culture",
            "travel_lifestyle",
        }.issubset(lanes))

    def test_feed_registry_has_unique_urls(self):
        urls = [feed["url"] for feed in FEED_SPECS]
        self.assertEqual(len(urls), len(set(urls)))

    def test_dedicated_saudi_interest_sources_are_present(self):
        urls = {feed["url"] for feed in FEED_SPECS}
        self.assertIn("https://www.alyaum.com/rssFeed/1009", urls)
        self.assertIn("https://www.alwatan.com.sa/rssFeed/3", urls)
        self.assertIn("https://aawsat.com/feed/sport", urls)
        self.assertIn("https://aawsat.com/feed/culture", urls)
        self.assertIn("https://aawsat.com/feed/travel", urls)
        self.assertIn("https://www.alyaum.com/rssFeed/1007/105", urls)
```

- [ ] **Step 2: Run the configuration tests and verify they fail**

Run:

```bash
python -m unittest tests.test_news_editorial.NewsEditorialTests.test_lane_targets_cover_sixty_model_slots -v
```

Expected: import failure because `news_editorial.py` does not exist yet.

- [ ] **Step 3: Implement the feed registry and lane targets**

Create `news_editorial.py` with the existing feeds plus the approved Saudi-interest feeds. Use dictionaries so every feed carries a lane explicitly:

```python
LANE_TARGETS = {
    "business_tech": 20,
    "saudi_core": 16,
    "sports": 8,
    "entertainment_culture": 8,
    "travel_lifestyle": 8,
}

FEED_SPECS = (
    {"source": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml", "lane": "business_tech"},
    {"source": "BBC Technology", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "lane": "business_tech"},
    {"source": "TechCrunch", "url": "https://techcrunch.com/feed/", "lane": "business_tech"},
    {"source": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "lane": "business_tech"},
    {"source": "Engadget", "url": "https://www.engadget.com/rss.xml", "lane": "business_tech"},
    {"source": "CNBC", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "lane": "business_tech"},
    {"source": "CNBC Tech", "url": "https://www.cnbc.com/id/19854910/device/rss/rss.html", "lane": "business_tech"},
    {"source": "الشرق الأوسط", "url": "https://aawsat.com/feed", "lane": "saudi_core"},
    {"source": "اليوم", "url": "https://www.alyaum.com/rssFeed/1005", "lane": "saudi_core"},
    {"source": "BBC عربي", "url": "https://feeds.bbci.co.uk/arabic/rss.xml", "lane": "saudi_core"},
    {"source": "اليوم - الرياضة", "url": "https://www.alyaum.com/rssFeed/1009", "lane": "sports"},
    {"source": "اليوم - الدوري السعودي", "url": "https://www.alyaum.com/rssFeed/1009/112", "lane": "sports"},
    {"source": "الوطن - رياضة", "url": "https://www.alwatan.com.sa/rssFeed/3", "lane": "sports"},
    {"source": "الشرق الأوسط - الرياضة", "url": "https://aawsat.com/feed/sport", "lane": "sports"},
    {"source": "الوطن - حياة", "url": "https://www.alwatan.com.sa/rssFeed/10", "lane": "entertainment_culture"},
    {"source": "الشرق الأوسط - الثقافة", "url": "https://aawsat.com/feed/culture", "lane": "entertainment_culture"},
    {"source": "الشرق الأوسط - أنغام وفنون", "url": "https://aawsat.com/feed/arts", "lane": "entertainment_culture"},
    {"source": "الشرق الأوسط - السينما", "url": "https://aawsat.com/feed/cinema", "lane": "entertainment_culture"},
    {"source": "اليوم - سياحة وسفر", "url": "https://www.alyaum.com/rssFeed/1007/105", "lane": "travel_lifestyle"},
    {"source": "الشرق الأوسط - السياحة", "url": "https://aawsat.com/feed/travel", "lane": "travel_lifestyle"},
    {"source": "اليوم - الحياة", "url": "https://www.alyaum.com/rssFeed/1007", "lane": "travel_lifestyle"},
)
```

Do not duplicate `الوطن - حياة` in both culture and lifestyle; one feed URL gets one lane so URL uniqueness and cross-feed deduplication stay predictable.

- [ ] **Step 4: Write failing audience-fit tests for hyperlocal/routine noise**

Append:

```python
    def test_hyperlocal_municipal_project_is_filtered(self):
        item = {
            "lane": "saudi_core",
            "title": "بلدية محافظة صغيرة تدشن ممشى جديداً في أحد الأحياء",
            "summary": "المشروع يتضمن تشجيراً وإنارة ومقاعد لخدمة سكان الحي.",
        }
        self.assertFalse(audience_fit_eligible(item))

    def test_major_airport_story_is_not_filtered_as_local(self):
        item = {
            "lane": "saudi_core",
            "title": "مطار الملك سلمان يعلن مرحلة جديدة تستوعب ملايين المسافرين",
            "summary": "التطوير يرتبط بحركة السفر والطيران على مستوى المملكة.",
        }
        self.assertTrue(audience_fit_eligible(item))

    def test_routine_cooperation_pr_is_filtered(self):
        item = {
            "lane": "saudi_core",
            "title": "جهتان تبحثان أوجه التعاون وتوقعان مذكرة تفاهم",
            "summary": "ناقش الاجتماع فرص التعاون المستقبلية بين الطرفين.",
        }
        self.assertFalse(audience_fit_eligible(item))

    def test_familiar_consumer_technology_story_survives_gate(self):
        item = {
            "lane": "business_tech",
            "title": "Apple ترفع سعر iPhone في السعودية",
            "summary": "السعر الجديد أعلى بـ200 ريال عند الإطلاق.",
        }
        self.assertTrue(audience_fit_eligible(item))
```

- [ ] **Step 5: Run the audience-fit tests and verify they fail**

Run:

```bash
python -m unittest \
  tests.test_news_editorial.NewsEditorialTests.test_hyperlocal_municipal_project_is_filtered \
  tests.test_news_editorial.NewsEditorialTests.test_major_airport_story_is_not_filtered_as_local \
  tests.test_news_editorial.NewsEditorialTests.test_routine_cooperation_pr_is_filtered -v
```

Expected: failure because `audience_fit_eligible` is not implemented.

- [ ] **Step 6: Implement the minimal deterministic gate**

Use a deliberately conservative gate: remove only obvious hyperlocal/routine noise and leave nuanced audience judgment to the model. The gate must not try to “understand all news” with keywords.

```python
import re

_LOCAL_ROUTINE_RE = re.compile(
    r"(?:بلدية|أمانة|حي\b|حديقة|ممشى|تشجير|سفلتة|إنارة|دوار|مواقف)"
)
_BROAD_RELEVANCE_RE = re.compile(
    r"(?:السعودية|المملكة|ساما|وزارة|هيئة|مطار|طيران|تأشيرة|تمويل|قرض|"
    r"رهن|إسكان|أسعار|رسوم|ضريبة|بنك|موسم الرياض|نيوم|القدية|العلا)"
)
_ROUTINE_PR_RE = re.compile(
    r"(?:بحث(?:ا|ت|وا)?\s+(?:أوجه\s+)?التعاون|مذكرة تفاهم|اجتماع.*التعاون|"
    r"استعراض فرص التعاون)"
)
_IMPACT_RE = re.compile(
    r"(?:إطلاق|إلغاء|خفض|رفع|زيادة|انخفاض|سعر|رسوم|قرار|نظام|تمويل|"
    r"استحواذ|اكتتاب|تأشيرة|رحلات|مطار|مليار|مليون|%)"
)


def audience_fit_eligible(item):
    text = f"{item.get('title', '')} {item.get('summary', '')}".strip()
    lane = item.get("lane", "business_tech")

    if _ROUTINE_PR_RE.search(text) and not _IMPACT_RE.search(text):
        return False

    if lane == "saudi_core":
        if _LOCAL_ROUTINE_RE.search(text) and not _BROAD_RELEVANCE_RE.search(text):
            return False

    return True
```

The gate intentionally does **not** reject a story simply for naming Riyadh, Jeddah, Dammam, etc. Location is not the problem; narrow scale/routine content is.

- [ ] **Step 7: Run Task 1 tests and verify they pass**

Run:

```bash
python -m unittest tests.test_news_editorial -v
```

Expected: all Task 1 tests PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add news_editorial.py tests/test_news_editorial.py
git commit -m "feat: add Saudi Snapchat news source policy"
```

---

### Task 2: Add lane-aware, source-fair shortlist construction

**Files:**
- Modify: `news_editorial.py`
- Modify: `tests/test_news_editorial.py`

**Interfaces:**
- Consumes: `audience_fit_eligible(item: dict) -> bool`, `LANE_TARGETS`.
- Produces: `balanced_shortlist(items: list[dict], limit: int = 60) -> list[dict]`.
- Produces: `shortlist_lane_counts(items: list[dict]) -> dict[str, int]`.
- `news_bot.py` will consume both in Task 4.

- [ ] **Step 1: Write failing shortlist tests**

Append tests using a helper:

```python
    def make_item(self, lane, n, source=None, title=None):
        return {
            "lane": lane,
            "source": source or f"source-{lane}",
            "title": title or f"{lane} story {n}",
            "summary": f"meaningful development {n}",
            "link": f"https://example.com/{lane}/{n}",
        }

    def test_balanced_shortlist_represents_all_populated_lanes(self):
        from news_editorial import balanced_shortlist, shortlist_lane_counts

        items = []
        for lane in LANE_TARGETS:
            items.extend(self.make_item(lane, i) for i in range(20))

        shortlist = balanced_shortlist(items, 60)
        counts = shortlist_lane_counts(shortlist)

        self.assertEqual(len(shortlist), 60)
        self.assertEqual(counts["business_tech"], 20)
        self.assertEqual(counts["saudi_core"], 16)
        self.assertEqual(counts["sports"], 8)
        self.assertEqual(counts["entertainment_culture"], 8)
        self.assertEqual(counts["travel_lifestyle"], 8)

    def test_unused_lane_capacity_flows_to_other_qualified_lanes(self):
        from news_editorial import balanced_shortlist, shortlist_lane_counts

        items = [self.make_item("business_tech", i) for i in range(80)]
        items += [self.make_item("saudi_core", i) for i in range(4)]

        shortlist = balanced_shortlist(items, 60)
        counts = shortlist_lane_counts(shortlist)

        self.assertEqual(len(shortlist), 60)
        self.assertEqual(counts["saudi_core"], 4)
        self.assertEqual(counts["business_tech"], 56)

    def test_hyperlocal_items_do_not_fill_saudi_core_target(self):
        from news_editorial import balanced_shortlist, shortlist_lane_counts

        weak = [
            {
                "lane": "saudi_core",
                "source": "local",
                "title": f"بلدية محافظة تدشن ممشى جديداً في حي {i}",
                "summary": "تشجير وإنارة لخدمة الحي.",
                "link": f"https://example.com/local/{i}",
            }
            for i in range(20)
        ]
        strong = [self.make_item("business_tech", i) for i in range(60)]

        shortlist = balanced_shortlist(weak + strong, 60)
        counts = shortlist_lane_counts(shortlist)
        self.assertEqual(counts.get("saudi_core", 0), 0)
        self.assertEqual(counts["business_tech"], 60)

    def test_one_source_cannot_monopolize_lane_before_peer_source_gets_turn(self):
        from news_editorial import balanced_shortlist

        items = [self.make_item("sports", i, source="sports-a") for i in range(20)]
        items += [self.make_item("sports", 100 + i, source="sports-b") for i in range(4)]
        items += [self.make_item("business_tech", i, source="tech") for i in range(52)]

        shortlist = balanced_shortlist(items, 60)
        first_sports = [x["source"] for x in shortlist if x["lane"] == "sports"][:4]
        self.assertIn("sports-a", first_sports)
        self.assertIn("sports-b", first_sports)

    def test_duplicate_title_from_general_and_section_feed_appears_once(self):
        from news_editorial import balanced_shortlist

        duplicate = "الهلال يعلن صفقة كبرى للموسم الجديد"
        items = [
            self.make_item("saudi_core", 1, source="general", title=duplicate),
            self.make_item("sports", 2, source="sports", title=duplicate),
            self.make_item("business_tech", 3, source="tech"),
        ]
        shortlist = balanced_shortlist(items, 60)
        titles = [x["title"] for x in shortlist]
        self.assertEqual(titles.count(duplicate), 1)
```

- [ ] **Step 2: Run shortlist tests and verify they fail**

Run:

```bash
python -m unittest tests.test_news_editorial -v
```

Expected: failures because `balanced_shortlist` and `shortlist_lane_counts` do not exist.

- [ ] **Step 3: Implement title normalization and per-source round-robin queues**

Add:

```python
from collections import defaultdict, deque


def _title_key(title):
    return re.sub(r"\W+", "", (title or "").casefold())[:120]


def _dedupe_candidates(items):
    seen = set()
    result = []
    for item in items:
        key = _title_key(item.get("title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _lane_source_queues(items):
    by_lane = defaultdict(lambda: defaultdict(deque))
    for item in items:
        by_lane[item.get("lane", "business_tech")][item.get("source", "unknown")].append(item)
    return by_lane


def _pop_lane_item(source_queues, cursor):
    sources = list(source_queues)
    if not sources:
        return None, cursor
    for offset in range(len(sources)):
        idx = (cursor + offset) % len(sources)
        source = sources[idx]
        queue = source_queues[source]
        if queue:
            return queue.popleft(), (idx + 1) % len(sources)
    return None, cursor
```

- [ ] **Step 4: Implement balanced selection with first-pass targets and spillover**

Use lane interleaving so input order does not favor whichever lane happens to appear first in the registry:

```python
def balanced_shortlist(items, limit=60):
    qualified = [item for item in items if audience_fit_eligible(item)]
    qualified = _dedupe_candidates(qualified)
    queues = _lane_source_queues(qualified)
    lane_order = [lane for lane in LANE_TARGETS if queues.get(lane)]
    cursors = {lane: 0 for lane in lane_order}
    counts = defaultdict(int)
    selected = []

    # First pass: give every populated lane turns up to its target.
    progress = True
    while len(selected) < limit and progress:
        progress = False
        for lane in lane_order:
            if len(selected) >= limit:
                break
            if counts[lane] >= LANE_TARGETS[lane]:
                continue
            item, cursors[lane] = _pop_lane_item(queues[lane], cursors[lane])
            if item is not None:
                selected.append(item)
                counts[lane] += 1
                progress = True

    # Spillover: unused capacity goes to any lane with qualified leftovers.
    progress = True
    while len(selected) < limit and progress:
        progress = False
        for lane in lane_order:
            if len(selected) >= limit:
                break
            item, cursors[lane] = _pop_lane_item(queues[lane], cursors[lane])
            if item is not None:
                selected.append(item)
                counts[lane] += 1
                progress = True

    return selected


def shortlist_lane_counts(items):
    counts = defaultdict(int)
    for item in items:
        counts[item.get("lane", "business_tech")] += 1
    return dict(counts)
```

- [ ] **Step 5: Run shortlist tests and verify they pass**

Run:

```bash
python -m unittest tests.test_news_editorial -v
```

Expected: all Task 1–2 tests PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add news_editorial.py tests/test_news_editorial.py
git commit -m "feat: balance news candidates across audience lanes"
```

---

### Task 3: Replace the business-first prompt with the approved Saudi Snapchat 25–50 editorial model

**Files:**
- Modify: `news_editorial.py`
- Modify: `tests/test_news_editorial.py`
- Modify later in Task 4: `news_bot.py` to import the prompt.

**Interfaces:**
- Produces: `SYSTEM_PROMPT: str` containing `{n}` placeholders exactly as the current `news_bot.py` prompt expects.
- `news_bot.py` continues to call `SYSTEM_PROMPT.format(n=CANDIDATES)`.

- [ ] **Step 1: Write deterministic prompt-policy tests**

Append:

```python
    def test_prompt_targets_saudi_snapchat_adults_25_to_50(self):
        from news_editorial import SYSTEM_PROMPT
        self.assertIn("25", SYSTEM_PROMPT)
        self.assertIn("50", SYSTEM_PROMPT)
        self.assertIn("سناب شات", SYSTEM_PROMPT)
        self.assertIn("جمهور سعودي", SYSTEM_PROMPT)

    def test_prompt_allows_major_sports_entertainment_and_travel(self):
        from news_editorial import SYSTEM_PROMPT
        self.assertIn("الرياضة", SYSTEM_PROMPT)
        self.assertIn("الترفيه", SYSTEM_PROMPT)
        self.assertIn("السفر", SYSTEM_PROMPT)
        self.assertIn("الهلال", SYSTEM_PROMPT)
        self.assertIn("موسم الرياض", SYSTEM_PROMPT)

    def test_prompt_rejects_hyperlocal_and_routine_content(self):
        from news_editorial import SYSTEM_PROMPT
        self.assertIn("المشروع البلدي", SYSTEM_PROMPT)
        self.assertIn("محلي ضيق", SYSTEM_PROMPT)
        self.assertIn("الشائعات", SYSTEM_PROMPT)
        self.assertIn("نتائج المباريات الروتينية", SYSTEM_PROMPT)
        self.assertIn("ثرثرة المشاهير", SYSTEM_PROMPT)

    def test_prompt_no_longer_bans_sports_and_entertainment_wholesale(self):
        from news_editorial import SYSTEM_PROMPT
        self.assertNotIn("الرياضة والمشاهير والفن", SYSTEM_PROMPT)
```

- [ ] **Step 2: Run prompt tests and verify they fail**

Run:

```bash
python -m unittest tests.test_news_editorial -v
```

Expected: failure because `SYSTEM_PROMPT` has not been moved/rewritten yet.

- [ ] **Step 3: Add the new editorial-selection block**

In `news_editorial.py`, define the front half of `SYSTEM_PROMPT` with the approved audience and ranking rules. The exact block should include the following text and examples; keep it concise enough that the existing output/accuracy rules still fit comfortably in the token budget:

```python
_EDITORIAL_RULES = r"""أنت محرر محتوى إخباري يُنشر على سناب شات لجمهور سعودي بالغ،
غالبية جمهوره بين 25 و50 سنة. تكتب بالعربية دائماً حتى لو كان المصدر بالإنجليزية.

مهمتك ليست اختيار "أهم خبر في الصحف"، بل اختيار الخبر الحقيقي الذي سيجعل هذا
الجمهور يتوقف بين سنابات أصدقائه لأنه يمس حياته، أو يعرف الاسم جيداً، أو يفاجئه،
أو يعطيه شيئاً يستحق أن يتحدث عنه.

اختبر كل خبر داخلياً على: ملاءمة عمر 25-50، الصلة بالسعودية، شهرة الاسم، الأثر
على المال أو العمل أو السكن أو التقنية أو السفر أو العائلة أو الترفيه أو الرياضة،
قيمة الحديث والمشاركة، عنصر الجِدة، حجم الأثر، وإمكانية شرحه بصرياً بسرعة.

السعودي لا يعني المحلي فقط. لا تعطِ أولوية لخبر لأنه حدث داخل المملكة. المشروع
البلدي الصغير، ممشى أو حديقة في حي، سفلتة أو إنارة محلية، افتتاح بروتوكولي، أو
إعلان يهم مدينة أو جمهوراً محلياً ضيقاً لا يستحق بطاقة وطنية ما لم تكن دلالته
أوسع بكثير من موقعه.

اختر من هذه المجالات عندما يكون الخبر قوياً فعلاً:
- قرارات سعودية كبيرة تمس الحياة اليومية أو المستهلك أو العمل أو السكن أو الخدمات
- المال والأعمال: فائدة، تمويل، بنوك، أسعار، رسوم، اكتتابات، صفقات وشركات معروفة
- التقنية والذكاء الاصطناعي والمنتجات التي يستخدمها الناس
- الرياضة الكبرى ذات الحديث الواسع: الهلال، النصر، الاتحاد، الأهلي، المنتخب،
  صفقة كبيرة، بطولة كبرى أو قرار استثنائي؛ لا تحوّل الحساب إلى صفحة نتائج
- الترفيه والثقافة والأحداث الكبرى مثل موسم الرياض أو فعالية وطنية واسعة؛ لا
  تنشر ثرثرة المشاهير أو أخبار العلاقات أو المؤثرين بلا قيمة
- السفر والطيران والتأشيرات والمطارات والوجهات والفنادق والتغييرات التي تهم
  المسافرين فعلاً

استبعد: السياسة الحزبية، الحروب والصراعات، الجريمة والحوادث والكوارث، الشائعات
والتسريبات غير المؤكدة، نتائج المباريات الروتينية والمواعيد والتشكيلات، الانتقالات
الصغيرة، الإعلانات الترويجية العادية، الاجتماعات ومذكرات التفاهم بلا نتيجة ملموسة،
ثرثرة المشاهير، المؤثرين بلا قيمة، التحديثات التقنية الصغيرة، والشركات المجهولة.

اختبار التوقف: لو ظهر الخبر بين سنابات أصدقاء القارئ، هل سيتوقف لأنه يعني له
شيئاً أو لأنه يريد فوراً أن يعرف ماذا حدث؟ إن لم يكن، استبعده مهما كان صحيحاً.
ولا تصنع التوقف بعنوان مثير لخبر ضعيف.

أمثلة ترتيب:
✓ صفقة كبيرة للهلال أو النصر قد تتقدم على نتائج شركة أمريكية مغمورة.
✓ إعلان كبير لموسم الرياض قد يتقدم على تعديل صغير في واجهة Google.
✓ قرار تمويل أو رهن سعودي يمس الناس يتقدم على خبر اقتصادي سياسي بعيد.
✓ خبر كبير من Apple أو OpenAI قد يتقدم على إعلان بروتوكولي سعودي روتيني.
✗ نتيجة مباراة عادية لا تتقدم على خبر قوي يمس المال أو التقنية أو السفر.
✗ مشروع بلدي محدود في مدينة لا يتقدم لأنه سعودي فقط.

رتّب {n} أخبار من الأقوى لهذا الجمهور إلى الأقل. الخبر الأول هو المرشح للنشر
والبقية بدائل للصورة. لا تختر خبرين عن الحدث نفسه.
"""
```

- [ ] **Step 4: Preserve the current output, accuracy, naming, finance, and image-query rules verbatim**

From the current `news_bot.py` `SYSTEM_PROMPT`, copy the block beginning with:

```text
لكل خبر اكتب:
```

through the final JSON-only response instruction into a second constant named `_OUTPUT_AND_ACCURACY_RULES`. Do not rewrite those rules in this task; they already encode the important character limits, `takeaway` behavior, numerical comparisons, public-finance neutrality, naming conventions, image-query constraints, and JSON schema.

Then compose:

```python
SYSTEM_PROMPT = _EDITORIAL_RULES + "\n\n" + _OUTPUT_AND_ACCURACY_RULES
```

Delete the old business-first selection paragraphs from `news_bot.py` in Task 4 rather than leaving two competing editorial policies in production.

- [ ] **Step 5: Run prompt-policy tests and verify they pass**

Run:

```bash
python -m unittest tests.test_news_editorial -v
```

Expected: all prompt tests PASS, including the test proving the old wholesale sports/entertainment ban is absent.

- [ ] **Step 6: Commit Task 3**

```bash
git add news_editorial.py tests/test_news_editorial.py
git commit -m "feat: tailor news editor to Saudi Snapchat adults"
```

---

### Task 4: Integrate lane-tagged feeds and balanced shortlist into `news_bot.py`

**Files:**
- Modify: `news_bot.py` (config section around the current `FEEDS`, `fetch_headlines()`, `SYSTEM_PROMPT`, and `summarize()`)
- Modify: `tests/test_news_editorial.py`

**Interfaces:**
- Consumes from `news_editorial.py`: `FEED_SPECS`, `SYSTEM_PROMPT`, `balanced_shortlist`, `shortlist_lane_counts`.
- Preserves: `summarize(items, already_posted=(), pinned="")` signature and return schema.
- Internal fetched item adds `lane: str`; no public card field is added.

- [ ] **Step 1: Write a failing integration test for lane propagation and cross-feed dedupe**

Append:

```python
    def test_fetch_headlines_carries_lane_and_dedupes_section_overlap(self):
        from unittest.mock import patch
        import news_bot

        rss = b"""<?xml version='1.0'?>
        <rss><channel><item>
          <title>خبر سعودي مهم</title>
          <description>تغيير واسع يمس المستخدمين</description>
          <link>https://example.com/story</link>
        </item></channel></rss>"""

        specs = (
            {"source": "general", "url": "https://example.com/general", "lane": "saudi_core"},
            {"source": "section", "url": "https://example.com/section", "lane": "sports"},
        )

        with patch.object(news_bot, "FEED_SPECS", specs), \
             patch.object(news_bot, "_http_get", side_effect=[rss, rss]):
            items = news_bot.fetch_headlines()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["lane"], "saudi_core")
```

This preserves first-seen ownership of a duplicate title; `balanced_shortlist` also has a second dedupe layer for safety.

- [ ] **Step 2: Run the integration test and verify it fails**

Run:

```bash
python -m unittest \
  tests.test_news_editorial.NewsEditorialTests.test_fetch_headlines_carries_lane_and_dedupes_section_overlap -v
```

Expected: failure because `news_bot.py` still uses the old two-tuple `FEEDS` list and does not attach `lane`.

- [ ] **Step 3: Replace local feed/prompt definitions with imports**

Near the imports in `news_bot.py`, add:

```python
from news_editorial import (
    FEED_SPECS,
    SYSTEM_PROMPT,
    balanced_shortlist,
    shortlist_lane_counts,
)
```

Remove the old `FEEDS = [...]` block and the old in-file `SYSTEM_PROMPT = """..."""` block. Do not leave aliases that can drift from `news_editorial.py`.

- [ ] **Step 4: Make `fetch_headlines()` carry the internal lane**

Change:

```python
for source, url in FEEDS:
```

to:

```python
for feed in FEED_SPECS:
    source = feed["source"]
    url = feed["url"]
    lane = feed["lane"]
```

and add the lane to each fetched item:

```python
items.append({
    "source": source,
    "lane": lane,
    "title": title,
    "summary": _clean(field(
        "description", "{http://www.w3.org/2005/Atom}summary"))[:400],
    "link": field("link", "{http://www.w3.org/2005/Atom}link"),
})
```

Keep the existing date cutoff, failure handling, and first-seen title deduplication unchanged.

- [ ] **Step 5: Use the balanced shortlist before constructing the model message**

At the start of `summarize()` replace:

```python
shortlist = items[:MAX_HEADLINES_TO_MODEL]
```

with:

```python
shortlist = balanced_shortlist(items, MAX_HEADLINES_TO_MODEL)
counts = shortlist_lane_counts(shortlist)
if shortlist:
    print("    model shortlist: " + ", ".join(
        f"{lane}={counts.get(lane, 0)}" for lane in (
            "business_tech",
            "saudi_core",
            "sports",
            "entertainment_culture",
            "travel_lifestyle",
        )
    ))
```

Include lane context in the model input without changing the public output schema:

```python
feed_text = "\n".join(
    f"{n}. [{i['lane']} | {i['source']}] {i['title']} — {i['summary']}"
    for n, i in enumerate(shortlist, 1)
)
```

When mapping returned `item` numbers back to links, continue using the balanced `shortlist` exactly as the function already maps against the old shortlist.

- [ ] **Step 6: Run the integration and editorial unit tests**

Run:

```bash
python -m unittest tests.test_news_editorial -v
```

Expected: all tests PASS.

- [ ] **Step 7: Compile-check the touched production modules**

Run:

```bash
python -m py_compile news_editorial.py news_bot.py breaking_watch.py
```

Expected: exit code 0, no output.

- [ ] **Step 8: Commit Task 4**

```bash
git add news_bot.py news_editorial.py tests/test_news_editorial.py
git commit -m "feat: feed balanced Saudi audience candidates to news bot"
```

---

### Task 5: Verify feed health, audience mix, and regressions before enabling normal scheduled behavior

**Files:**
- Modify only if verification exposes a concrete defect: `news_editorial.py`, `news_bot.py`, or `tests/test_news_editorial.py`.
- No workflow schedule/publishing changes are planned.

**Interfaces:**
- Verifies all previous tasks as one working unit.

- [ ] **Step 1: Run the entire repository test suite**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: all existing and new tests PASS. Do not accept unrelated regressions in `test_batch_review.py`, `test_publish_cards.py`, `test_runtime_relevance.py`, or `test_simple_review.py`.

- [ ] **Step 2: Run a live feed-only smoke check without Claude or posting**

The feed fetcher does not require Anthropic or posting keys. Run:

```bash
python - <<'PY'
import news_bot
from news_editorial import balanced_shortlist, shortlist_lane_counts

items = news_bot.fetch_headlines()
shortlist = balanced_shortlist(items, news_bot.MAX_HEADLINES_TO_MODEL)
print("TOTAL FETCHED", len(items))
print("SHORTLIST", len(shortlist))
print("LANES", shortlist_lane_counts(shortlist))
for lane in ("sports", "entertainment_culture", "travel_lifestyle"):
    sample = [x["title"] for x in shortlist if x.get("lane") == lane][:3]
    print(lane, sample)
PY
```

Expected:
- feed failures are isolated/logged rather than crashing the run;
- at least the currently healthy Saudi-interest feeds contribute fresh items when they have published within `LOOKBACK_HOURS`;
- no lane is padded with hyperlocal municipal items merely to hit its target;
- if a lane has no fresh/qualified items, its capacity flows elsewhere.

If an approved feed consistently returns malformed XML or zero usable items during this smoke check, remove that feed from `FEED_SPECS` and add a test asserting the replacement URL/lane. Do not replace it with an unverified aggregator.

- [ ] **Step 3: Inspect the shortlist specifically for 25–50 audience fit**

From the smoke-check output, verify manually that the shortlist is not dominated by:
- neighborhood/municipality projects;
- routine club scores/fixtures;
- ordinary concert promotions;
- influencer/youth-only chatter;
- ceremonial meetings or memoranda with no consequence.

If one of those patterns repeatedly survives, add one narrow regression fixture to `tests/test_news_editorial.py` and the smallest corresponding gate/prompt rule. Do not grow the deterministic keyword gate into a second news-ranking engine.

- [ ] **Step 4: Run a real dry run through the existing workflow path**

With the repository's normal secrets available, run the existing `daily.yml` workflow manually with `dry_run=true` and `post=false`, or locally with the same environment variables and `DRY_RUN=1`.

Expected evidence in the log:
- per-feed recent-item counts include the new Saudi-interest sources;
- a `model shortlist:` line reports the lane mix;
- the selected headline is relevant to the Saudi 25–50 audience rather than simply the first globally important business headline;
- generated card still uses the existing `headline` / `summary` / `takeaway` schema and photo pipeline;
- nothing is posted to Snapchat.

- [ ] **Step 5: Compare at least three dry-run selections against the approved editorial examples**

Use three different candidate mixes/runs where practical and verify:
1. a major Saudi sports/event/travel story can beat remote global corporate news;
2. a major Apple/OpenAI/consumer story can beat routine Saudi PR;
3. a hyperlocal Saudi project does not win merely because it is local.

Record the observed winner and top alternatives in the implementation review/PR description rather than adding telemetry to production in Phase 1.

- [ ] **Step 6: Re-run tests after any smoke-test adjustment**

Run:

```bash
python -m unittest discover -s tests -v
python -m py_compile news_editorial.py news_bot.py breaking_watch.py
```

Expected: all tests PASS and compilation succeeds.

- [ ] **Step 7: Commit only if verification required code/feed adjustments**

If changes were necessary:

```bash
git add news_editorial.py news_bot.py tests/test_news_editorial.py
git commit -m "fix: tune Saudi Snapchat audience candidate quality"
```

If no changes were necessary, do not create an empty verification commit.

---

## Final Acceptance Checklist

Before merging/enabling the revised editorial behavior, verify all of the following:

- [ ] `FEED_SPECS` contains the existing strong business/tech/general sources plus dedicated Saudi sports, culture/entertainment, and travel/lifestyle sources.
- [ ] Every feed has exactly one internal lane and every URL is unique.
- [ ] `fetch_headlines()` preserves cross-feed deduplication and adds `lane` internally.
- [ ] Obvious hyperlocal municipal/routine cooperation items are filtered before lane allocation.
- [ ] `balanced_shortlist()` represents populated lanes up to the initial targets and reallocates unused capacity to qualified leftovers.
- [ ] A single source receives round-robin turns rather than monopolizing its lane before peers are sampled.
- [ ] The prompt explicitly targets Saudi Snapchat adults aged 25–50.
- [ ] The prompt allows major sports, entertainment/culture, travel, and lifestyle stories without turning the account into sports/gossip/trending content.
- [ ] The prompt explicitly rejects hyperlocal low-scale news, routine sports, gossip, rumors, minor tech updates, and ceremonial PR.
- [ ] Existing output/accuracy/public-finance/naming/image-query rules remain intact.
- [ ] Public JSON and renderer/publishing interfaces are unchanged.
- [ ] `breaking_watch.py` compiles and its confirmation threshold/source architecture is not changed in Phase 1.
- [ ] Full unit suite passes.
- [ ] Live feed smoke check shows sensible lane representation.
- [ ] At least one no-post dry run produces a card successfully with the revised selection logic.
