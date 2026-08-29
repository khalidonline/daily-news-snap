# Automatic Relevant Image Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `auto` the default daily-news image mode so production is not pinned to SPA while retaining manual source overrides and all existing image safeguards.

**Architecture:** Keep the large `news_bot.py` image pipeline unchanged. Add a small normalization helper in `daily_news_runner.py` that sets `news_bot_module.IMAGE_SOURCE` before `news_bot.main()` runs, and change `daily.yml` so both manual and scheduled runs default to `auto`.

**Tech Stack:** Python 3.12, `unittest`, GitHub Actions YAML.

**Spec:** `docs/superpowers/specs/2026-08-29-auto-image-source-design.md`

## Global Constraints

- Default daily image mode is `auto`.
- Preserve explicit overrides: `article`, `spa`, `commons`, `loc`, `openverse`, `stock`, `none`.
- Normalize `pexels` to `stock`.
- Blank or unsupported values become `auto`.
- Do not change image safety, scoring, licensing, rendering, publishing, or breaking-news logic.

---

### Task 1: Add runner image-source policy

**Files:**
- Modify: `daily_news_runner.py`
- Modify: `tests/test_news_editorial.py`

**Interfaces:**
- Produce: `normalize_image_source(value: str | None) -> str`
- `configure(news_bot_module)` sets `news_bot_module.IMAGE_SOURCE` using this helper.

- [ ] **Step 1: Write failing tests**

Add tests that assert:

```python
self.assertEqual(daily_news_runner.normalize_image_source(None), "auto")
self.assertEqual(daily_news_runner.normalize_image_source(""), "auto")
self.assertEqual(daily_news_runner.normalize_image_source("spa"), "spa")
self.assertEqual(daily_news_runner.normalize_image_source("pexels"), "stock")
self.assertEqual(daily_news_runner.normalize_image_source("bogus"), "auto")
```

Also extend the existing `configure()` test to assert `fake.IMAGE_SOURCE == "auto"` when the environment variable is absent, and add an override test with `IMAGE_SOURCE=commons`.

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m unittest tests.test_news_editorial -v
```

Expected: failure because `normalize_image_source` does not exist and `configure()` does not set `IMAGE_SOURCE`.

- [ ] **Step 3: Implement minimal policy**

Add:

```python
SUPPORTED_IMAGE_SOURCES = {
    "auto", "article", "spa", "commons", "loc", "openverse", "stock", "none"
}


def normalize_image_source(value):
    value = (value or "").strip().lower()
    if value == "pexels":
        value = "stock"
    return value if value in SUPPORTED_IMAGE_SOURCES else "auto"
```

In `configure()` add:

```python
news_bot_module.IMAGE_SOURCE = normalize_image_source(os.getenv("IMAGE_SOURCE", "auto"))
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python -m unittest tests.test_news_editorial -v
python -m py_compile daily_news_runner.py
```

Expected: all focused tests pass and compilation succeeds.

---

### Task 2: Make workflow default to auto

**Files:**
- Modify: `.github/workflows/daily.yml`

**Interfaces:**
- Manual `image_source` input default: `auto`.
- Scheduled fallback environment value: `auto`.

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

Confirm the only `daily.yml` behavior changes are the added `auto` option, the new default, and the scheduled fallback. Do not change schedule/posting controls.

---

### Task 3: Regression verification

**Files:**
- No production changes unless verification exposes a defect.

- [ ] **Step 1: Run editorial tests and compilation**

```bash
python -m unittest tests.test_news_editorial -v
python -m py_compile news_editorial.py daily_news_runner.py
```

- [ ] **Step 2: Review branch diff**

Verify `news_bot.py`, `breaking.yml`, rendering code, and publishing code are unchanged.

- [ ] **Step 3: Open PR and let the existing News editorial tests workflow run**

Expected: green CI before merge.

- [ ] **Step 4: Dry-run after merge**

Run `News brief to Snapchat` manually with `dry_run=true`, `post=false`, and `image_source=auto`. Confirm the log prints the normal multi-source photo order rather than moving SPA to the front via a workflow override, and inspect the generated card for subject relevance.
