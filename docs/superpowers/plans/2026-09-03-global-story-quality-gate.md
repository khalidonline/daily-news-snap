# Global Story Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent subject drift, misleading claims, broken chronology, and old/ambiguous ending visuals from reaching the human Story reviewer.

**Architecture:** Add a side-effect-free `story_quality_gate.py` that evaluates the final six editorial frame payloads together with final visual-state evidence. Integrate it after rendering and frame relevance, but before the review manifest is frozen; BLOCK findings downgrade the candidate to internal REVIEW and produce targeted repair instructions. Preserve the existing cost guard, editorial cache, Telegram approval gate, and exact frozen-file delivery.

**Tech Stack:** Python 3.12, pathlib, re, existing Story visual-state and publishability modules, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-03-global-story-quality-gate-design.md`

## Global Constraints

- No Jeddah-, SAMA-, Riyadh-, company-, or title-specific exception may be added to the new gate.
- Existing frame relevance remains authoritative for semantic image fit.
- Telegram remains blocked until human approval of the exact frozen deck.
- Approved delivery must reuse the existing SHA-256 manifest and must never rerender.
- The new quality evaluator makes no network, Telegram, Snapchat, image-generation, or paid-model calls.
- Deterministic copy and metadata checks run first; unresolved explicitly current endings fail closed rather than buying a vision call.
- Existing Story editorial call guards and cache behavior remain unchanged.
- A quality-blocked deck must not be frozen with `status=READY`.
- Visual-only failures produce frame-targeted visual repair instructions; editorial failures are marked for targeted editorial repair and do not automatically trigger a paid regeneration.

---

### Task 1: Deterministic global Story quality evaluator

**Files:**
- Create: `story_quality_gate.py`
- Test: `tests/test_story_quality_gate.py`

**Interfaces:**
- Produces: `QUALITY_POLICY = "story-quality-v1"`
- Produces: `evaluate_story_quality(story: str, frames: list[dict], visual_state: dict) -> dict`
- Produces: `release_ready(report: dict) -> bool`
- Produces: `repair_target(report: dict) -> dict`

- [ ] **Step 1: Write failing tests covering multiple Story types**

Create fixtures using six frame dicts and matching `visual_state["frames"][str(i)]` rows. Cover:

```python
def test_airport_side_topic_drift_is_blocked():
    frames = focused_airport_frames()
    frames[0]["heading"] = "الحج كان يأتي من البحر"
    frames[0]["text"] = "كان القادمون إلى مكة يصلون بحراً..."
    report = sqg.evaluate_story_quality("قصة أول مطار في جدة وتطور الطيران المدني", frames, visual_state(frames))
    self.assertFalse(sqg.release_ready(report))
    self.assertFinding(report, "subject_focus", 1)


def test_company_founder_tangent_is_blocked():
    frames = focused_company_frames()
    frames[2] = frame("طفولة المؤسس", "قصة عائلته ومدرسته لا تشرح تطور الشركة", ["family portrait"])
    report = sqg.evaluate_story_quality("قصة شركة أكمي وتطورها", frames, visual_state(frames))
    self.assertFinding(report, "subject_focus", 3)


def test_unsupported_exclusivity_is_blocked():
    frames = focused_airport_frames()
    frames[1]["text"] += " وكان هذا الطريق الوحيد للوصول."
    report = sqg.evaluate_story_quality("قصة مطار جدة", frames, visual_state(frames))
    self.assertFinding(report, "claim_precision", 2)


def test_saudi_geography_ambiguity_is_blocked():
    frames = focused_airport_frames()
    frames[1]["text"] = "بدأ الطيران التجاري في الجزيرة."
    report = sqg.evaluate_story_quality("قصة مطار جدة في السعودية", frames, visual_state(frames))
    self.assertFinding(report, "claim_precision", 2)


def test_dates_must_not_regress_without_flashback():
    frames = historical_frames([1945, 1981, 1990, 2000, 2020, 1975])
    report = sqg.evaluate_story_quality("قصة تطور مطار المدينة", frames, visual_state(frames))
    self.assertFinding(report, "narrative_chronology", 6)


def test_current_final_frame_requires_positive_modern_visual_evidence():
    frames = historical_airport_frames()
    frames[-1]["text"] = "اليوم أصبح المطار بوابة حديثة للسعودية."
    frames[-1]["image_keywords"] = ["airport historic archive"]
    report = sqg.evaluate_story_quality("قصة مطار المدينة", frames, visual_state(frames))
    self.assertFinding(report, "final_frame_currency", 6)
```

Also cover: valid supporting context returns to subject, 1945→1981→current passes, current final with `Terminal 1`/modern evidence passes, timeless frame with unknown era passes, flashback cue permits a date regression, and visual-only failure generates only that frame in repair target.

- [ ] **Step 2: Run RED**

Run: `python -m unittest -v tests/test_story_quality_gate.py`
Expected: FAIL because `story_quality_gate` does not exist.

- [ ] **Step 3: Implement deterministic evaluator**

Implementation rules:
- tokenize Arabic/Latin text with `re` only;
- derive meaningful subject tokens from Story title after removing generic Story/connector stopwords;
- classify frame focus from heading+text+punch+image keywords using subject-token overlap and supporting transition cues;
- frame 1 and 6 require direct subject evidence;
- block clear DRIFT and more than two consecutive supporting frames;
- block high-risk exclusivity/universality patterns such as `الوحيد`, `الوحيدة`, `حصراً`, `فقط` when used as an exclusivity claim, `دائماً`, `الجميع`, `أبداً`;
- block standalone `الجزيرة` in a Saudi-context Story unless it is explicitly `شبه الجزيرة`;
- extract 18xx/19xx/20xx years and block unexplained regressions; allow explicit flashback cues such as `قبل ذلك`, `نعود`, `بالعودة`;
- identify current-copy cues (`اليوم`, `حالياً`, `الآن`, `في الوقت الحالي`, `today`, `currently`, `now`);
- derive visual-era evidence from `frame_payload` image keywords plus visual-state source/metadata strings;
- archival cues include `historic`, `historical`, `archive`, `old`, `vintage`, `قديم` and old explicit years;
- modern cues include `modern`, `current`, `today`, `terminal 1`, `terminal1`, `حديث`, and explicit years >= 2015;
- an explicitly current final frame requires positive modern evidence; archive or unknown evidence blocks;
- evaluator returns dimensions, structured findings, per-frame focus/time/visual-era evidence, and a repair target.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest -v tests/test_story_quality_gate.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add story_quality_gate.py tests/test_story_quality_gate.py
git commit -m "feat: add global Story quality evaluator"
```

---

### Task 2: Enforce quality before human-review freeze

**Files:**
- Modify: `guarded_story_publish.py`
- Test: `tests/test_story_quality_gate_integration.py`

**Interfaces:**
- Consumes: `story_quality_gate.evaluate_story_quality`
- Consumes: `story_quality_gate.release_ready`
- Persists in visual state: `story_quality_policy`, `story_quality_status`, `story_quality_findings`, `story_quality_repair`

- [ ] **Step 1: Write failing integration tests**

Test a helper that receives final frame payloads and visual state, proving:
- technical READY + quality PASS => `READY`;
- technical READY + quality BLOCK => `REVIEW`;
- quality BLOCK is persisted before review-manifest creation;
- the quality module does not call notification/publish functions.

Use dependency injection / patched save function, not a full renderer subprocess.

- [ ] **Step 2: Run RED**

Run: `POST_TO_SNAPCHAT=0 python -m unittest -v tests/test_story_quality_gate_integration.py`
Expected: FAIL because the quality gate is not wired into the release boundary.

- [ ] **Step 3: Integrate at the post-render boundary**

In `guarded_story_publish.py`:
1. load final `visual_state`;
2. build `frame_payloads` from each visual-state row;
3. evaluate global quality;
4. set final status to `READY` only when both existing visual accounting and global quality pass;
5. persist quality evidence into the same revision state;
6. then call `_persist_current_publishability` and `write_review_manifest`.

A blocked quality report must print a compact diagnostic such as:

```text
STORY_QUALITY_GATE: BLOCKED policy=story-quality-v1 frames=[1,6]
STORY_QUALITY_REPAIR: { ... }
```

Do not invoke editorial regeneration or visual repair from this gate. It only returns/persists targets.

- [ ] **Step 4: Run integration + existing review tests GREEN**

Run:
`POST_TO_SNAPCHAT=0 python -m unittest -v tests/test_story_quality_gate_integration.py tests/test_story_review_gate.py tests/test_story_publishability.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add guarded_story_publish.py tests/test_story_quality_gate_integration.py
git commit -m "feat: block weak Stories before human review"
```

---

### Task 3: CI coverage and cost-preservation regression

**Files:**
- Modify: `.github/workflows/story-publishability-ci.yml`
- Modify: `.github/workflows/story-cost-control-tests.yml`
- Test: existing suites plus `tests/test_story_quality_gate.py` and integration test

**Interfaces:** none new.

- [ ] **Step 1: Add new files to CI path filters and test commands**

`story-publishability-ci.yml` must run both new quality suites. `story-cost-control-tests.yml` must include `story_quality_gate.py` in its path filters and run the quality tests without API credentials.

- [ ] **Step 2: Add a regression that imports/evaluates the quality gate with no model/network environment**

The test should patch or remove model-related environment variables and prove evaluation still returns synchronously from local data.

- [ ] **Step 3: Run the focused suite**

Run:
`python -m unittest -v tests/test_story_quality_gate.py tests/test_story_quality_gate_integration.py tests/test_story_cost_guard.py tests/test_story_review_gate.py tests/test_story_publishability.py`
Expected: PASS.

- [ ] **Step 4: Run the full Story CI matrix on the PR head**

Require success from:
- Story publishability tests
- Runtime relevance tests
- Story cost-control tests
- Story visual accounting test
- Personal Story visual policy test

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/story-publishability-ci.yml .github/workflows/story-cost-control-tests.yml
git commit -m "ci: enforce global Story quality gate"
```

---

### Task 4: Production proof with Jeddah as a regression, not an exception

**Files:** no production story-specific code.

- [ ] **Step 1: Run Jeddah in review-only mode after merge**

Use the existing cached editorial brief, `POST_TO_SNAPCHAT=0`, `STORY_HUMAN_APPROVED=0`, `DRY_RUN=1`, and no explicit editorial-regeneration nonce.

- [ ] **Step 2: Verify no fresh editorial generation is purchased**

Expected log: `EDITORIAL_CACHE_HIT ...`; no new paid editorial reservation/result for the same revision.

- [ ] **Step 3: Verify the old Jeddah deck is blocked before human-ready review**

Expected: global quality report blocks at least one of subject focus / claim precision / current final-frame visual evidence; review manifest status is not `READY`; Telegram and Snapchat untouched.

- [ ] **Step 4: Verify repair targets are frame-scoped**

Expected structured output identifies only affected editorial/visual frames and does not request full-deck regeneration by default.

- [ ] **Step 5: Record proof in PR/merge notes**

No Jeddah-specific rule should appear in `story_quality_gate.py`.
