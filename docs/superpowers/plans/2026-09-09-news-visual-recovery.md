# News Visual Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure an editorially approved scheduled News story is not dropped because its first image searches fail, using only verified real photos, exact portraits, exact logos, or approved reusable context photographs.

**Architecture:** Add a focused `news_visual_recovery.py` module that validates model-supplied visual targets and resolves exact local logos without fuzzy brand matching. Extend the existing single editorial response with typed fallback targets, then let `daily_news_runner.py` exhaust portrait, logo, metadata-backed and same-subject reuse tiers for the top-ranked story.

**Tech Stack:** Python 3.12, standard library, Pillow, existing image providers and vision gate, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-09-news-visual-recovery-design.md`

## Global Constraints

- AI-generated imagery is not allowed.
- The top-ranked editorial story stays fixed during visual recovery.
- Wrong entities, people, product models, generic filler, graphics, unsafe or unlicensed images are never promoted.
- Exact-subject reuse is allowed only after fresh sources fail.
- No additional paid text-model response is introduced.
- Pexels remains optional and its 403 cannot cancel delivery.
- Topic, Story, Breaking and direct Snapchat publishing behavior remain unchanged.

---

### Task 1: Typed targets and exact logos

**Files:**
- Create: `news_visual_recovery.py`
- Create: `tests/test_news_visual_recovery.py`
- Read: `images/logos/index.json`

**Interfaces:**
- Produce: `normalize_visual_targets(story: dict) -> list[dict[str, str]]`
- Produce: `exact_logo_for_targets(targets: list[dict], logos_dir: Path, index_path: Path) -> tuple[Path | None, str | None]`
- Target shape: `{"kind": "person|organization|place|object|context", "name_en": str, "name_ar": str}`

- [ ] Write failing tests proving allowed kinds only, blank removal, deduplication, an eight-target cap, and legacy query fallback to `context` targets.
- [ ] Run `python -m unittest tests.test_news_visual_recovery.NewsVisualRecoveryTests -v`; verify import failure because the module is absent.
- [ ] Implement deterministic normalization. Never infer a person or organization from untyped free text.
- [ ] Write failing logo tests for OpenAI success, unknown failure, and rejection of misleading secondary aliases such as Google under Yahoo and Uber under Careem.
- [ ] Implement lookup that considers only `organization` targets and requires equality with the canonical key or first canonical alias; prefer `*-current.*`.
- [ ] Run the tests and commit with `git commit -m "Add typed News visual targets"`.

---

### Task 2: Plan recovery targets in the existing editorial response

**Files:**
- Modify: `news_editorial_prompt.txt`
- Modify: `daily_news_runner.py`
- Modify: `tests/test_news_editorial.py`

**Interfaces:**
- Consumes: `normalize_visual_targets(story)`
- Produces: normalized `visual_targets` on every remembered story

- [ ] Write failing tests requiring the prompt to request typed visual targets in fallback order and `remember_story_contexts()` to preserve their normalized form.
- [ ] Run `python -m unittest tests.test_news_editorial.DailyNewsRunnerTests -v` and verify the new assertions fail.
- [ ] Add `visual_targets` to the existing JSON story object. People and organizations must be explicitly named in the source; context targets cannot claim to depict the event.
- [ ] Normalize targets before storing `_STORY_CONTEXTS`; do not make another model call.
- [ ] Run the tests and commit with `git commit -m "Plan visual fallbacks during News selection"`.

---

### Task 3: Portrait, logo and scoped-reuse recovery

**Files:**
- Modify: `daily_news_runner.py`
- Modify: `daily_news_fresh_runner.py`
- Modify: `tests/test_auto_image_selector.py`
- Modify: `tests/test_photo_reuse_fallback.py`

**Interfaces:**
- Consumes: normalized `visual_targets`
- Consumes: existing `fetch_commons_portrait(name, out_path)` when available
- Consumes: existing `fetch_local_photo(..., respect_cooldown=False)`
- Consumes: `exact_logo_for_targets(...)`
- Produces: a selected `(photo_path, credit)` or `(None, None)` after exhaustive recovery

- [ ] Write failing tests proving named-person targets try strict Commons portraits and named-organization targets promote only exact current logos with an `.exempt` marker.
- [ ] Prove Google cannot receive Yahoo and Uber cannot receive Careem.
- [ ] Run `python -m unittest tests.test_auto_image_selector.RelevanceFirstWrapperTests -v` and verify RED.
- [ ] After fresh providers and guarded metadata-neutral candidates, try exact portraits and exact logos. Preserve portrait credit and mark logos exempt from photo cooldown.
- [ ] Write failing tests proving same-story recent reuse works after fresh exhaustion but cannot leak to another story or entity.
- [ ] Move reuse inside the auto-selector invocation, bind it to normalized targets, and remove indiscriminate scheduled deletion of valid same-story candidates.
- [ ] Run `python -m unittest tests.test_auto_image_selector tests.test_photo_reuse_fallback -v` and commit with `git commit -m "Recover News visuals with portraits logos and scoped reuse"`.

---

### Task 4: Keep the top story independent of image convenience

**Files:**
- Modify: `news_bot.py`
- Modify: `daily_news_fresh_runner.py`
- Modify: `tests/test_news_visual_recovery.py`
- Modify: `tests/test_daily_review_workflow.py`

**Interfaces:**
- Produce: `NEWS_LOCK_TOP_STORY_VISUAL`, installed only by `daily_news_fresh_runner`
- Scheduled News searches only `stories[:1]` when the flag is active

- [ ] Write a failing main-loop test with two stories where the first succeeds only through recovery and the second has an easy photo; assert the first renders.
- [ ] Write a failing test requiring unrecoverable infrastructure errors to name the selected story instead of claiming several items lacked photos.
- [ ] Set the News-only policy flag and limit the visual loop only for scheduled News. Keep all other flows unchanged.
- [ ] Run `python -m unittest tests.test_news_visual_recovery tests.test_daily_review_workflow -v` and commit with `git commit -m "Keep News selection independent of image convenience"`.

---

### Task 5: Verify and integrate

**Files:**
- Modify only if verification exposes a regression

**Interfaces:**
- Produces: merge-ready branch `fix/news-neutral-photo-fallback`

- [ ] Run the complete News test command from `.github/workflows/news-editorial-tests.yml`, adding `tests.test_news_visual_recovery`.
- [ ] Run `python -m py_compile news_visual_recovery.py news_editorial.py daily_news_runner.py daily_news_fresh_runner.py news_bot.py daily_slot_scheduler.py shared_schedule_gate.py`.
- [ ] Run `git diff --check` and inspect the final diff against every spec requirement.
- [ ] Push the branch, create PR `Guarantee News visual recovery`, wait for required checks, and merge into `main`.
