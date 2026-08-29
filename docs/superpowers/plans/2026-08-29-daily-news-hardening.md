# Daily News Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent out-of-scope stories from surviving the daily editorial pipeline and make automatic image selection use a safe neutral photograph when no direct-match photograph exists.

**Architecture:** Keep `news_bot.py`'s renderer, publishing, provider implementations and breaking path intact. Put deterministic scope and feed-quality logic in `news_editorial.py`; put post-model validation and cross-provider automatic image orchestration in `daily_news_runner.py`. In `auto` image mode the runner will use the existing provider implementations and existing `photo_shows()` judge, but it will compare provider candidates before returning one to the legacy selector.

**Tech Stack:** Python 3.12, `unittest`, GitHub Actions, existing RSS/XML helpers, existing image provider functions and Anthropic vision gate.

**Spec:** `docs/superpowers/specs/2026-08-29-daily-news-hardening-design.md`

## Global Constraints

- Daily-news audience remains Saudi/Arabic Snapchat adults roughly 25–50.
- Normal-news age ceiling remains 48 hours.
- Lane targets remain maximum opportunities, never quotas.
- Hard scope boundaries cannot be overridden by the model.
- Macro finance such as Fed rates, inflation, oil and major market moves remains eligible when materially relevant.
- `auto` image mode uses relevance tier before provider source.
- Image order is `yes` > safe `neutral` > reject `no`.
- Preserve image licensing, safety, quality, Saudi-context, cooldown, provenance and credit rules.
- Manual image-source overrides retain legacy behavior.
- Pexels remains optional; a Pexels credential failure cannot kill the run.
- Do not change `breaking.yml`, posting frequency, card renderer, publisher interfaces or public story JSON schema.

---

### Task 1: Hard scope filter before lane allocation

**Files:**
- Modify: `news_editorial.py`
- Modify: `tests/test_news_editorial.py`

**Interfaces:**
- Produce: `hard_scope_eligible(item: dict) -> bool`.
- `audience_fit_eligible(item)` continues to own routine/local quality rules.
- `balanced_shortlist()` requires both gates plus freshness.

- [ ] **Step 1: Write failing production-regression tests**

Add tests using the exact failure shapes from #86/#87:

```python
def test_foreign_political_control_story_is_hard_rejected(self):
    item = self.make_item(
        "business_tech", 1, source="BBC",
        title="ترامب يعلن اتفاقاً أمريكياً للسيطرة على نفط فنزويلا",
        summary="اتفاق سياسي جديد يتعلق بفنزويلا والنفط.")
    self.assertFalse(hard_scope_eligible(item))


def test_medical_advice_story_is_hard_rejected(self):
    item = self.make_item(
        "travel_lifestyle", 2,
        title="التوقف المفاجئ عن أدوية ضغط الدم له 5 مخاطر",
        summary="نصائح طبية عن الأدوية وضغط الدم.")
    self.assertFalse(hard_scope_eligible(item))


def test_routine_hilal_result_is_hard_rejected(self):
    item = self.make_item(
        "sports", 3,
        title="الهلال يسحق الخليج بخماسية في دوري روشن",
        summary="فاز الهلال بنتيجة كبيرة في مباراة دوري عادية.")
    self.assertFalse(hard_scope_eligible(item))


def test_obscure_company_borrowing_for_nvidia_is_hard_rejected(self):
    item = self.make_item(
        "business_tech", 4, source="TechCrunch",
        title="شركة Lambda تقترض مليار دولار لشراء رقائق NVIDIA",
        summary="شركة حوسبة غير معروفة تقترض لشراء الرقائق.")
    self.assertFalse(hard_scope_eligible(item))
```

Add positive controls:

```python
def test_fed_rate_story_remains_eligible(self):
    item = self.make_item(
        "business_tech", 5,
        title="الاحتياطي الفيدرالي يلمح لاحتمال رفع الفائدة مجدداً",
        summary="القرار المحتمل يؤثر في أسعار الفائدة والتمويل والأسواق.")
    self.assertTrue(hard_scope_eligible(item))


def test_major_saudi_property_story_remains_eligible(self):
    item = self.make_item(
        "saudi_core", 6,
        title="اهتمام دولي متزايد بشراء العقارات في السعودية",
        summary="تغير ملحوظ في الطلب على السوق السعودية.")
    self.assertTrue(hard_scope_eligible(item))


def test_major_championship_story_remains_eligible(self):
    item = self.make_item(
        "sports", 7,
        title="الهلال يتوج بلقب دوري أبطال آسيا بعد النهائي",
        summary="لقب قاري كبير للنادي السعودي.")
    self.assertTrue(hard_scope_eligible(item))


def test_national_saudi_health_policy_remains_eligible(self):
    item = self.make_item(
        "saudi_core", 8,
        title="السعودية توسع التغطية التأمينية لخدمة ملايين المستفيدين",
        summary="تغيير وطني في التأمين الصحي والخدمات.")
    self.assertTrue(hard_scope_eligible(item))
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m unittest tests.test_news_editorial.NewsEditorialTests -v
```

Expected: new tests fail because `hard_scope_eligible` does not exist.

- [ ] **Step 3: Implement minimal hard-scope patterns**

Add narrow compiled patterns for:

- foreign political/geopolitical main-subject terms and named high-profile foreign political figures;
- medical advice/treatment terms with a `saudi_core` national-policy exception;
- weather terms;
- routine sports result language with championship/final/qualification/record exceptions;
- unfamiliar-company financing/borrowing/fundraising patterns with a known-company/macro/Saudi exception.

Do not turn this into a general keyword ranking engine. The function is a hard exclusion layer only.

- [ ] **Step 4: Apply the gate in `balanced_shortlist()`**

Change qualification to require:

```python
hard_scope_eligible(item)
and audience_fit_eligible(item)
and freshness_eligible(item, now=now)
```

- [ ] **Step 5: Verify GREEN and commit**

Run the full editorial suite, then commit only Task 1 files.

---

### Task 2: Post-model hard validation

**Files:**
- Modify: `daily_news_runner.py`
- Modify: `tests/test_news_editorial.py`

**Interfaces:**
- Import: `hard_scope_eligible` from `news_editorial`.
- Produce: `validate_ranked_result(result: dict, shortlist: list[dict]) -> dict`.
- `make_summarizer()` calls the validator before `remember_story_contexts()`.

- [ ] **Step 1: Write failing tests**

Cover:

```python
def test_post_model_validation_removes_hard_ineligible_item_even_if_ranked_first():
    shortlist = [political_item, strong_saudi_item]
    result = {"stories": [
        {"item": 1, "headline": "bad"},
        {"item": 2, "headline": "good"},
    ]}
    filtered = daily_news_runner.validate_ranked_result(result, shortlist)
    self.assertEqual([s["item"] for s in filtered["stories"]], [2])
```

Also reject item `0`, negative values, non-integers and values larger than the shortlist; preserve order and unrelated top-level keys.

- [ ] **Step 2: Verify RED**

Expected failure: validator missing.

- [ ] **Step 3: Implement minimal validator**

Map the model's 1-based `item` to the exact shortlist source item. Keep only stories whose item number is valid and whose source item passes `hard_scope_eligible()` and `audience_fit_eligible()`.

- [ ] **Step 4: Integrate after `original_summarize()`**

For normal feed mode:

```python
raw = original_summarize(decorated, already_posted, pinned)
validated = validate_ranked_result(raw, shortlist)
return remember_story_contexts(validated)
```

Pinned/breaking behavior stays unchanged.

- [ ] **Step 5: Verify GREEN and commit**

Run editorial tests and compile checks.

---

### Task 3: Cross-source automatic image selection with neutral fallback

**Files:**
- Modify: `daily_news_runner.py`
- Modify: `tests/test_auto_image_selector.py`

**Interfaces:**
- `remember_story_contexts()` stores enough returned story data to recover `headline`, `summary`, `takeaway`, `link`, `scope`, English queries and Arabic queries.
- `install_auto_image_selector(news_bot_module)` keeps original provider functions, then replaces the local fetch entrypoint with an auto orchestrator.
- Produce internal helpers for candidate temp paths, promotion and marker cleanup/copying.

- [ ] **Step 1: Replace the old `yes`-only expectation with failing desired-behavior tests**

Tests must prove:

1. article/local `neutral`, later SPA/Commons `yes` => later `yes` wins;
2. no `yes`, first safe `neutral` exists => first neutral is promoted;
3. all candidates `no`/missing => no image;
4. a neutral Commons/SPA/article candidate keeps its real provider credit, never `Pexels`;
5. local `.exempt` provenance is copied when that local neutral/yes is selected;
6. `.recentkeep` is not accidentally attached to a different provider's selected image;
7. after auto orchestration the legacy provider loop is suppressed for that story, avoiding duplicate network searches.

- [ ] **Step 2: Verify RED**

Expected: neutral-fallback tests fail under the current `verdict == "yes"` wrappers.

- [ ] **Step 3: Implement candidate isolation**

For each provider, call its saved original implementation using a provider-specific temporary JPG path. All existing provider safety/licence/quality checks still run inside those originals.

Search providers in this logical order:

```python
local, article, spa-if-saudi, commons, loc, openverse, stock-if-key
```

Use the story recovered from the query-key map for link/scope/context.

- [ ] **Step 4: Implement relevance tiers**

For each returned candidate:

```python
verdict = str(news_bot_module.photo_shows(path, context)).strip().lower()
```

- `yes`: promote immediately and return `(hero_path, real_credit)`;
- first `neutral`: copy to a neutral stash with credit/provenance, then continue;
- `no`: discard;
- exhausted with no `yes`: promote the stashed neutral;
- no acceptable candidate: return `(None, None)`.

- [ ] **Step 5: Preserve marker sidecars**

When promoting a candidate, replace the hero file and copy only marker sidecars belonging to that candidate (`.exempt`, `.generated`, `.recentkeep` when present). Clear stale hero markers first so one provider can never inherit another provider's provenance.

- [ ] **Step 6: Prevent duplicate legacy searching**

The auto local orchestrator runs the whole provider pool. Wrapped downstream provider functions return no result for the same story after that orchestration. If story context cannot be resolved, fall back to the legacy provider behavior rather than inventing context.

- [ ] **Step 7: Verify GREEN and commit**

Run both editorial and image-selector suites.

---

### Task 4: Feed-ingestion reliability

**Files:**
- Modify: `news_editorial.py`
- Modify: `tests/test_news_editorial.py`

**Interfaces:**
- Produce: internal `_parse_feed_root(raw: bytes | str)` helper.
- `fetch_headlines()` skips entries without a parsed publication timestamp.

- [ ] **Step 1: Write failing malformed-feed and undated-item tests**

Use an RSS fixture containing a bare ampersand in description text:

```xml
<description>رياض & سفر</description>
```

Assert the item is recovered after sanitation. Add an undated fixture and assert it never appears in returned daily items.

- [ ] **Step 2: Verify RED**

Bare ampersand should currently trigger an XML parse failure; undated item currently enters `fetch_headlines()`.

- [ ] **Step 3: Implement conservative retry sanitation**

Try strict XML first. On `ET.ParseError`, remove XML-illegal ASCII control characters and escape only bare ampersands that are not already valid entities, then retry. If retry fails, preserve existing feed-isolated error behavior.

- [ ] **Step 4: Drop undated items during fetch**

After `_parse_date`, `continue` when `published is None`. This makes feed counts and the 48-hour guarantee consistent.

- [ ] **Step 5: Verify GREEN and commit**

Run the full editorial suite.

---

### Task 5: Workflow consistency and Pexels degradation

**Files:**
- Modify: `.github/workflows/daily.yml`
- Optionally modify tests only if a code path changes.

- [ ] **Step 1: Fix the broad-scope label**

Change:

```yaml
BRIEF_TITLE: "ملخص تنفيذي - أعمال وتقنية"
```

to:

```yaml
BRIEF_TITLE: "ملخص تنفيذي - خبر"
```

Do not change schedule/posting controls.

- [ ] **Step 2: Confirm Pexels is optional**

No code may require a successful Pexels response when an earlier safe neutral candidate exists. Current Pexels docs use `Authorization: API_KEY`; a 403 is a credential/access problem, not a reason to weaken image safety or misattribute another source.

- [ ] **Step 3: Commit workflow-only change**

---

### Task 6: Branch-wide verification and production dry run

**Files:** none unless a regression is found.

- [ ] **Step 1: Run all focused tests**

```bash
python -m unittest tests.test_news_editorial tests.test_auto_image_selector -v
python -m py_compile news_editorial.py daily_news_runner.py
```

Expected: all pass.

- [ ] **Step 2: Review diff scope**

Confirm `breaking.yml`, card renderer and publisher code are unchanged.

- [ ] **Step 3: Open non-draft PR and require GitHub Actions GREEN**

- [ ] **Step 4: Merge after clean review**

- [ ] **Step 5: Run `News brief to Snapchat` manually on `main`**

Use `post=false`, `image_source=auto`. Inspect logs for:

- no Trump/Venezuela-style politics in ranked stories;
- no medical-advice story;
- no routine scoreline result;
- no Lambda-style obscure financing story;
- strong Saudi/property/consumer/major-tech/macro candidates remain;
- image search logs show later `yes` beating earlier `neutral`, or `neutral fallback` when no `yes` exists;
- a card is produced when a safe neutral exists;
- no provider is miscredited.

- [ ] **Step 6: If live run exposes another reproducible defect, add a failing regression first, fix it, rerun CI, and repeat the manual dry run before completion.**
