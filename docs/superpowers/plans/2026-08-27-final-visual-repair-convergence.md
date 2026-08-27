# Final Visual Repair Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing bounded visual-repair system converge efficiently by isolating durable advisory history, prioritizing near-PASS work, routing logo-only stories correctly, applying typed source ordering, and emitting a richer deterministic full-board curation artifact without weakening any correctness gate.

**Architecture:** Keep PR #22's `tools/bulk_visual_failure_history.py` as the only persistent history implementation. Add sanitization and explicit path injection, then wire queue/source/curation behavior through the existing controller and single-story repair engine. Runtime coverage, validation, identity, provenance, duplicate, reviewer and registration layers remain untouched as PASS authority.

**Tech Stack:** Python 3.12, `unittest`, existing GitHub Actions workflows, existing `story_runtime`/`story_bot` modules.

**Spec:** `docs/superpowers/specs/2026-08-27-final-visual-repair-convergence.md`

## Global Constraints

- Authoritative runtime PASS baseline is 25/123 before this implementation.
- `story_runtime.coverage()` remains the sole PASS authority.
- PASS requires exactly 4 relevant usable local photos and 1 verified relevant local logo.
- Only DIRECT and STRONG_CONTEXT photo verdicts count.
- No guessed logos, no weakened identity checks, no provenance/license bypasses, and no cached acceptance.
- Per-story and per-source latency bounds remain unchanged.
- `state/bulk_visual_failure_history.json` is the only persistent failure-memory system.
- Do not run the live bulk-repair workflow during implementation.

---

### Task 1: Sanitize and isolate durable history

**Files:**
- Modify: `tools/bulk_visual_failure_history.py`
- Modify: `tests/test_bulk_visual_failure_history.py`
- Modify: `state/bulk_visual_failure_history.json`

**Interfaces:**
- Produces: `sanitize_history(history: dict, valid_stories: Collection[str]) -> dict`
- Produces: history APIs that accept an explicit `path` where persistence occurs.

- [ ] **Step 1: Write failing tests** proving fake story records are removed, real story records survive, ACCEPTED is never durable, transient diagnostics remain retryable, and explicit temporary paths leave the repository history byte-identical.
- [ ] **Step 2: Run** `python -m unittest -v tests/test_bulk_visual_failure_history.py` and confirm the new tests fail for missing sanitization/isolation behavior.
- [ ] **Step 3: Implement** `sanitize_history` as a pure bounded filter across `candidate_rejections`, `complete_query_sets`, and `diagnostics`; keep record ordering deterministic and never add coverage/approval fields.
- [ ] **Step 4: Ensure persistence functions use explicit `path` parameters consistently and production callers pass the production path; tests always pass temporary paths.**
- [ ] **Step 5: Replace polluted repository history with the sanitized result against the authoritative story catalogue, retaining legitimate production records only.**
- [ ] **Step 6: Re-run** `python -m unittest -v tests/test_bulk_visual_failure_history.py` and confirm green.

### Task 2: Convergent queue ordering and logo-only routing

**Files:**
- Modify: `tools/bulk_visual_queue.py`
- Modify: `tests/test_bulk_visual_queue.py`
- Modify: `tests/test_bulk_visual_repair.py`

**Interfaces:**
- `build_run_queue(rows, cursor, limit)` returns bands: logo-only, one-photo, one-photo+logo, larger deficits; rotation remains within equal-priority bands.
- `process_rows(...)` must not call photo repair when `need_photos == 0`.

- [ ] **Step 1: Write failing queue tests** for the four priority bands and within-band cursor rotation.
- [ ] **Step 2: Write a failing repair integration test** where a logo-only row records a logo attempt but the supplied photo-repair callable must never be invoked.
- [ ] **Step 3: Run** `python -m unittest -v tests/test_bulk_visual_queue.py tests/test_bulk_visual_repair.py` and confirm the new expectations fail.
- [ ] **Step 4: Implement minimal queue-band ordering and logo-only routing without changing mixed-row logo-before-photo behavior.**
- [ ] **Step 5: Re-run the targeted tests and confirm green.**

### Task 3: Typed source strategy

**Files:**
- Modify: `tools/bulk_visual_sources.py`
- Modify: `tools/bulk_visual_repair.py`
- Modify: `tests/test_bulk_visual_sources.py`
- Modify: `tests/test_bulk_visual_repair.py`

**Interfaces:**
- Produces: `story_source_strategy(story: str, beats=None) -> tuple[str, ...]`
- Consumes only existing typed beat metadata, explicit context, and verified logo domain.

- [ ] **Step 1: Write failing tests** for Saudi/Gulf company, person, company, historical/place, product/invention, and fallback adapter ordering.
- [ ] **Step 2: Add a failing repair test** proving adapter execution follows `story_source_strategy` while preserving source budgets and identity prefilters.
- [ ] **Step 3: Run** `python -m unittest -v tests/test_bulk_visual_sources.py tests/test_bulk_visual_repair.py` and confirm failures are due to missing typed ordering.
- [ ] **Step 4: Implement the deterministic strategy and integrate it into `repair_photos`; first-party is included only when a verified story logo domain exists.**
- [ ] **Step 5: Re-run targeted tests and confirm green.**

### Task 4: Rich controller-owned full-board curation

**Files:**
- Create: `tools/bulk_visual_curation.py`
- Modify: `tools/bulk_visual_run.py`
- Modify: `tests/test_bulk_visual_run.py`
- Modify: `tests/test_bulk_visual_failure_history.py`

**Interfaces:**
- Produces: `write_curation(rows, history, path) -> Path`
- Reads only board rows, typed beat metadata, strategy metadata, and advisory history.
- Never calls registration or runtime coverage mutation APIs.

- [ ] **Step 1: Write failing tests** that curation contains all unresolved rows, exact photo/logo deficits, typed identity/context, missing beats, bounded deterministic rejections, completed query-set/source pairs, constraints, and recommended source class.
- [ ] **Step 2: Add a failing test** proving writing/reading curation cannot alter runtime board/PASS state.
- [ ] **Step 3: Run** `python -m unittest -v tests/test_bulk_visual_run.py tests/test_bulk_visual_failure_history.py` and confirm failures.
- [ ] **Step 4: Implement deterministic `write_curation` and call it from controller finish paths using the complete `_final_board()` and loaded sanitized history.**
- [ ] **Step 5: Re-run targeted tests and confirm green.**

### Task 5: Full regression and PR verification

**Files:**
- Verify all modified files only; no live repair dispatch.

- [ ] **Step 1: Run full controller validation:** `python -m unittest -v tests/test_bulk_visual_*.py tests/test_runtime_relevance.py tests/test_apply_repair_assets.py`.
- [ ] **Step 2: Run static checks:** `python -m py_compile tools/bulk_visual_failure_history.py tools/bulk_visual_queue.py tools/bulk_visual_sources.py tools/bulk_visual_repair.py tools/bulk_visual_run.py tools/bulk_visual_curation.py` and `git diff --check`.
- [ ] **Step 3: Verify repository history is catalogue-only and contains no known fixture story such as `NVIDIA story`.**
- [ ] **Step 4: Compare branch to `repair/story-visual-coverage`; ensure no `images/**`, `stories.txt`, relevance ledger, publishing, reviewer threshold, identity/provenance gate, or workflow secret changes are present.**
- [ ] **Step 5: Open one draft PR against `repair/story-visual-coverage` summarizing the convergence changes and explicitly state that no live bulk-repair workflow was run during implementation.**
