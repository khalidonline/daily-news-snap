# Automatic Relevant Image Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `auto` the default daily-news image mode and make direct story relevance outrank image provider order.

**Architecture:** Keep `news_bot.py` unchanged. `daily_news_runner.py` will normalize image mode, retain story context after summarization, and wrap the existing image-provider functions only in `auto` mode. The legacy selector may still call providers sequentially, but wrappers will return only visually direct (`yes`) candidates immediately; `neutral` candidates are held while later providers are checked, and restored only if no `yes` candidate exists.

**Tech Stack:** Python 3.12, `unittest`, GitHub Actions YAML, existing Anthropic `photo_shows()` vision gate.

**Spec:** `docs/superpowers/specs/2026-08-29-auto-image-source-design.md`

## Global Constraints

- Default daily image mode is `auto`.
- Best relevant image wins; source is secondary.
- Preserve explicit overrides: `article`, `spa`, `commons`, `loc`, `openverse`, `stock`, `none`.
- Normalize `pexels` to `stock`.
- Blank or unsupported values become `auto`.
- `yes` beats `neutral`; `neutral` beats `no`.
- Do not change image safety, metadata scoring, licensing, rendering, publishing, photo cooldown, or breaking-news logic.
- Keep `news_bot.py` unchanged.

---

### Task 1: Add runner image-source policy and story context

**Files:**
- Modify: `daily_news_runner.py`
- Modify: `tests/test_news_editorial.py`

**Interfaces:**
- Produce: `normalize_image_source(value: str | None) -> str`
- Produce: internal story-context map keyed by normalized English image-query tuple.
- `configure(news_bot_module)` sets `news_bot_module.IMAGE_SOURCE` and installs relevance wrappers only for `auto`.

- [ ] **Step 1: Write failing normalization/configuration tests**

Assert:

```python
self.assertEqual(daily_news_runner.normalize_image_source(None), "auto")
self.assertEqual(daily_news_runner.normalize_image_source(""), "auto")
self.assertEqual(daily_news_runner.normalize_image_source("spa"), "spa")
self.assertEqual(daily_news_runner.normalize_image_source("pexels"), "stock")
self.assertEqual(daily_news_runner.normalize_image_source("bogus"), "auto")
```

Extend the existing `configure()` test to assert `fake.IMAGE_SOURCE == "auto"` when unset. Add an explicit `IMAGE_SOURCE=commons` test and verify automatic wrappers are not installed for that manual override.

- [ ] **Step 2: Verify RED**

Run the editorial suite and confirm the new tests fail because the policy does not exist.

- [ ] **Step 3: Implement normalization**

Add the supported-mode set and `normalize_image_source()`; set `news_bot_module.IMAGE_SOURCE` in `configure()`.

- [ ] **Step 4: Capture story context**

In `make_summarizer()`, after `original_summarize()` returns, store each returned story's context:

```python
context = "\n".join(x for x in (
    story.get("headline", ""),
    story.get("summary", ""),
    story.get("takeaway", ""),
) if x)
```

Key it by the normalized tuple of `story["image_queries"]` so provider wrappers can recover the real card text from the search queries they receive.

---

### Task 2: Relevance-first provider wrappers

**Files:**
- Modify: `daily_news_runner.py`
- Modify: `tests/test_news_editorial.py`

**Interfaces:**
- Produce: `install_auto_image_selector(news_bot_module)`.
- It wraps existing `fetch_local_photo`, `fetch_article_photo`, `fetch_spa_photo`, `fetch_commons_photo`, `fetch_loc_photo`, `fetch_openverse_photo`, and `fetch_photo` only when mode is `auto`.
- Originals remain callable inside wrappers.

- [ ] **Step 1: Write failing selection tests**

Use fake provider functions that write candidate files and a fake `photo_shows` judge. Cover:

1. local/article returns `neutral`, later SPA returns `yes` => SPA is returned;
2. early provider returns `no` => it is not returned;
3. no provider returns `yes`, one returns `neutral` => neutral is returned only at end of chain;
4. selected local candidate keeps `.exempt` provenance marker when promoted to the legacy hero path;
5. a provider-rejected recent photo's `.recentkeep` is propagated to the legacy hero path so existing cross-story fallback still works.

- [ ] **Step 2: Verify RED**

Run the focused tests and confirm failure because wrappers are not implemented.

- [ ] **Step 3: Implement candidate isolation**

Each wrapped provider calls its original implementation with a provider-specific temporary JPG path beside the legacy hero path. Existing provider safety/licence/score/cooldown checks therefore run unchanged.

- [ ] **Step 4: Apply vision relevance tiers**

For each fresh candidate call:

```python
verdict = news_bot_module.photo_shows(candidate_path, story_context)
```

- `yes`: promote candidate to the requested hero path and return it immediately;
- `neutral`: save first neutral candidate, return no photo so the legacy loop continues;
- `no`: reject and continue.

- [ ] **Step 5: Finalize the chain**

The final actually-called provider is Pexels when a key exists, otherwise Openverse. If it produces no `yes`, promote the stored neutral candidate. If there is no neutral but a provider left `.recentkeep`, copy that to the requested hero `.recentkeep` and return no photo so the existing `recent_fallback()` logic remains authoritative.

- [ ] **Step 6: Verify GREEN**

Run the full editorial tests and compilation check.

---

### Task 3: Make workflow default to auto

**Files:**
- Modify: `.github/workflows/daily.yml`

- [ ] **Step 1: Update workflow input**

Add `auto` as the first choice and change the default from `spa` to `auto`.

- [ ] **Step 2: Update scheduled fallback**

Change:

```yaml
IMAGE_SOURCE: ${{ inputs.image_source || 'spa' }}
```

to:

```yaml
IMAGE_SOURCE: ${{ inputs.image_source || 'auto' }}
```

- [ ] **Step 3: Verify workflow diff**

Do not change schedule, posting controls, image safety variables, or breaking workflow.

---

### Task 4: Regression verification

- [ ] **Step 1:** Run `python -m unittest tests.test_news_editorial -v`.
- [ ] **Step 2:** Run `python -m py_compile news_editorial.py daily_news_runner.py`.
- [ ] **Step 3:** Confirm `news_bot.py` and `breaking.yml` are unchanged.
- [ ] **Step 4:** Open PR and require the existing News editorial tests workflow to pass.
- [ ] **Step 5:** After merge, run `News brief to Snapchat` with `dry_run=true`, `post=false`, `image_source=auto` and inspect logs/card. The log should show that a neutral/rejected early-source image does not block a later directly relevant image.
