# Final Visual Repair Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing bounded visual-repair system converge efficiently by isolating durable advisory history, prioritizing near-PASS work, routing logo-only stories correctly, applying typed source ordering, and emitting a richer deterministic full-board curation artifact without weakening any correctness gate.

**Architecture:** Keep PR #22's `tools/bulk_visual_failure_history.py` as the only persistent history implementation. Add catalogue sanitization and explicit path injection, keep typed source ordering in the focused `tools/bulk_visual_strategy.py` module, and route curation through the existing controller/single-story boundary. Runtime coverage, validation, identity, provenance, duplicate, reviewer and registration layers remain unchanged as PASS authority.

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
- Modify: `tools/bulk_visual_repair.py`
- Test: `tests/test_bulk_visual_failure_history.py`
- Test: `tests/test_bulk_visual_convergence.py`

**Interfaces:**
- Produces: `sanitize_history(history: dict, valid_stories: Collection[str]) -> dict`
- Produces: `persist_query_set_complete(...)` that merges into the latest durable history.
- History APIs accept an explicit `path` so tests never need the production history file.

- [x] **Step 1: Write failing tests** proving fake story records are removed, real story records survive, ACCEPTED is never durable, transient diagnostics remain retryable, and explicit temporary paths leave the repository history byte-identical.
- [x] **Step 2: Observe the RED PR run** where the polluted `NVIDIA story` record suppresses a test discovery call.
- [x] **Step 3: Implement** `sanitize_history` as a pure bounded filter across `candidate_rejections`, `complete_query_sets`, and `diagnostics`; keep record ordering deterministic and never add coverage/approval fields.
- [x] **Step 4: Isolate injected/test history paths** and make custom repair attempt sinks ignore production failure memory unless an explicit history path is provided.
- [x] **Step 5: Sanitize production history once per repair process before it can suppress work.** The sanitized file is persisted immediately and then travels through the controller's existing history checkpoint path; legitimate production records are retained while non-catalogue fixture stories are removed.
- [x] **Step 6: Persist completed query fingerprints by reloading the latest file first**, so query completion cannot overwrite a deterministic rejection recorded by a preceding telemetry write.

### Task 2: Convergent queue ordering and logo-only routing

**Files:**
- Modify: `tools/bulk_visual_queue.py`
- Modify: `tests/test_bulk_visual_queue.py`
- Test: `tests/test_bulk_visual_convergence.py`

**Interfaces:**
- `build_run_queue(rows, cursor, limit)` returns bands: logo-only, one-photo, one-photo+logo, larger deficits; rotation remains within equal-priority bands.
- Existing `process_rows(...)` must not call photo repair when `need_photos == 0`.

- [x] **Step 1: Write failing queue tests** for the four priority bands and within-band cursor rotation.
- [x] **Step 2: Add a routing regression test** where a logo-only row cannot invoke the supplied photo-repair callable.
- [x] **Step 3: Observe RED ordering failures** on the pre-implementation PR head.
- [x] **Step 4: Implement minimal queue-band ordering** without changing mixed-row logo-before-photo behavior.
- [x] **Step 5: Verify the targeted behavior in the full PR test suite.**

### Task 3: Typed source strategy

**Files:**
- Create: `tools/bulk_visual_strategy.py`
- Modify: `tools/bulk_visual_repair.py`
- Test: `tests/test_bulk_visual_convergence.py`
- Preserve: `tools/bulk_visual_sources.py` adapter implementation and latency bounds.

**Interfaces:**
- Produces: `story_source_strategy(story: str, beats=None) -> tuple[str, ...]`
- Consumes only existing typed beat metadata, explicit context, story text, and verified logo domain.
- `repair_photos` filters the strategy through actually available adapters, so first-party discovery runs only when a verified story domain exists.

- [x] **Step 1: Write failing tests** for Saudi/Gulf company, person, company, historical/place, product/invention, and fallback adapter ordering.
- [x] **Step 2: Integrate strategy ordering into `repair_photos`** while preserving source budgets and identity prefilters.
- [x] **Step 3: Keep the source adapters themselves unchanged**, including Wikimedia policy handling, request limits, retries, identity filtering and same-name conflict logic.
- [x] **Step 4: Verify typed ordering and all existing source regressions in the full PR suite.**

### Task 4: Rich controller-owned full-board curation

**Files:**
- Create: `tools/bulk_visual_curation.py`
- Modify: `tools/bulk_visual_repair.py` curation dispatch used by the controller
- Test: `tests/test_bulk_visual_run.py`
- Test: `tests/test_bulk_visual_convergence.py`

**Interfaces:**
- Produces: `write_curation(rows, history, path) -> Path`
- Reads only board rows, typed beat metadata, strategy metadata, and advisory history.
- Never calls registration or runtime coverage mutation APIs.

- [x] **Step 1: Write tests** that curation contains all unresolved rows, exact photo/logo deficits, typed identity/context, missing beats, bounded deterministic rejections, completed query-set/source pairs, constraints, and recommended source class.
- [x] **Step 2: Add a test** proving curation output cannot mutate `CoverageRow`/PASS state.
- [x] **Step 3: Implement deterministic `write_curation`.**
- [x] **Step 4: Preserve the existing controller call that passes the complete `_final_board()`**, while `_write_unresolved(..., "curation-required.json")` dispatches to the richer writer with sanitized history.
- [x] **Step 5: Verify full-board controller and curation tests together.**

### Task 5: Full regression and PR verification

**Files:**
- Verify all modified files only; no live repair dispatch.

- [x] **Step 1: Run full controller validation in PR CI:** `python -m unittest -v tests/test_bulk_visual_*.py tests/test_runtime_relevance.py tests/test_apply_repair_assets.py`.
- [x] **Step 2: Verify Python imports/syntax through the same PR suite** and ensure the changed-file diff contains no generated visual assets or workflow changes.
- [x] **Step 3: Verify catalogue sanitization explicitly rejects the known fixture story `NVIDIA story` before production history can influence discovery.**
- [x] **Step 4: Compare branch to `repair/story-visual-coverage`; ensure no `images/**`, `stories.txt`, relevance ledger, publishing, reviewer threshold, identity/provenance gate, or workflow secret changes are present.**
- [x] **Step 5: Keep one draft PR against `repair/story-visual-coverage`; do not run the live bulk-repair workflow during implementation.**
