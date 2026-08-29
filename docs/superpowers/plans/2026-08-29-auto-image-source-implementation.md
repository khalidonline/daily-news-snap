# Automatic Relevant Image Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `auto` the default daily-news image mode and make direct story relevance outrank image provider order.

**Architecture:** Keep `news_bot.py` unchanged. `daily_news_runner.py` normalizes image mode, retains story context after summarization, and wraps the existing image-provider functions only in `auto` mode. The legacy selector still calls providers sequentially, but wrappers return a candidate only when the existing vision judge gives it a direct `yes`; `neutral` and `no` both fall through to later providers or later ranked stories.

**Tech Stack:** Python 3.12, `unittest`, GitHub Actions YAML, existing Anthropic `photo_shows()` vision gate.

**Spec:** `docs/superpowers/specs/2026-08-29-auto-image-source-design.md`

## Global Constraints

- Default daily image mode is `auto`.
- Best relevant image wins; source is secondary.
- Preserve explicit overrides: `article`, `spa`, `commons`, `loc`, `openverse`, `stock`, `none`.
- Normalize `pexels` to `stock`.
- Blank or unsupported values become `auto`.
- In `auto`, accept only `photo_shows(...) == "yes"`; reject `neutral` and `no`.
- Do not change image safety, metadata scoring, licensing, rendering, publishing, photo cooldown, or breaking-news logic.
- Keep `news_bot.py` unchanged.

---

### Task 1: Add runner image-source policy and story context

**Files:**
- Modify: `daily_news_runner.py`
- Test: `tests/test_auto_image_selector.py`

**Interfaces:**
- Produce: `normalize_image_source(value: str | None) -> str`.
- Produce: `remember_story_contexts(result)` using headline + summary + takeaway.
- `configure(news_bot_module)` sets `news_bot_module.IMAGE_SOURCE` and installs relevance wrappers only for `auto` when the module exposes the image-provider interfaces.

- [x] **Step 1: Write failing normalization/configuration tests**
- [x] **Step 2: Verify RED in GitHub Actions** — run `33240105573` failed only on missing new behavior while the existing editorial tests passed.
- [x] **Step 3: Implement normalization** — supported values, `pexels -> stock`, invalid/blank -> `auto`.
- [x] **Step 4: Capture story context** — map normalized English/Arabic image queries to the returned story's headline, summary and takeaway.
- [x] **Step 5: Guard installation for partial/test modules** — install wrappers only when all required image-provider functions and `photo_shows` are present.

---

### Task 2: Relevance-first provider wrappers

**Files:**
- Modify: `daily_news_runner.py`
- Test: `tests/test_auto_image_selector.py`

**Interfaces:**
- Produce: `install_auto_image_selector(news_bot_module)`.
- Wrap: `fetch_local_photo`, `fetch_article_photo`, `fetch_spa_photo`, `fetch_commons_photo`, `fetch_loc_photo`, `fetch_openverse_photo`, `fetch_photo` only in `auto` mode.
- Originals remain responsible for their existing licence, metadata, safety, geographic-context, minimum-score, graphic/document and cooldown checks.

- [x] **Step 1: Write failing selection tests** covering an early `neutral` vs later `yes`, early `no`, all-neutral rejection, metadata preservation, story-context content, and manual-override bypass.
- [x] **Step 2: Verify RED** in GitHub Actions run `33240105573`.
- [x] **Step 3: Implement wrappers around the existing provider functions** without modifying `news_bot.py`.
- [x] **Step 4: Apply the direct-match rule**:

```python
verdict = news_bot_module.photo_shows(photo, story_context)
return candidate only if verdict == "yes"
```

`neutral` and `no` both return no photo so the existing provider/story loop continues.

- [ ] **Step 5: Verify GREEN** with the full editorial + image-selector suite and compilation check.

---

### Task 3: Make workflow default to auto

**Files:**
- Modify: `.github/workflows/daily.yml`

- [x] **Step 1:** Add `auto` as the first manual choice and make it the default.
- [x] **Step 2:** Change scheduled/manual fallback to `${{ inputs.image_source || 'auto' }}`.
- [x] **Step 3:** Keep schedule, publishing controls, image thresholds and breaking workflow unchanged.

---

### Task 4: Regression verification and handoff

- [ ] **Step 1:** Require `python -m unittest tests.test_news_editorial tests.test_auto_image_selector -v` to pass.
- [ ] **Step 2:** Require `python -m py_compile news_editorial.py daily_news_runner.py` to pass.
- [ ] **Step 3:** Compare branch to `main` and confirm `news_bot.py` and `breaking.yml` are unchanged.
- [ ] **Step 4:** Open a PR and require the News editorial tests workflow to pass on the final head.
- [ ] **Step 5:** After merge, manually dry-run `News brief to Snapchat` with `dry_run=true`, `post=false`, `image_source=auto`. Confirm logs show `auto image relevance:` verdicts and that an early neutral/rejected image does not prevent a later directly relevant image from winning.
