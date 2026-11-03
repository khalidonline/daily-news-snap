# Text-card pre-display fit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Present only concise, template-measured information text cards for owner review.

**Architecture:** Extract the current renderer's exact Arabic wrapping/ink measurement into a shared pure module; use it from both the renderer and a draft-preparation CLI. Return character counts and actual line/height budgets, never a universal character limit that falsely guarantees fit. The assistant revises unapproved drafts internally and reruns the gate; no truncation or paid generation is introduced.

**Tech Stack:** Python, Pillow/RAQM, existing pinned Almarai fonts, pytest.

**Spec:** Khalid instruction 2026-11-03: pause design, shorten drafts and measure characters against the approved template BEFORE presenting a textual card. Root AGENTS.md and publishing_v2/design-settings.json remain authoritative.

## Global Constraints
- Preserve 44 Bold body, two lines maximum, one headline and closing line; no template, palette or font-size changes.
- Preserve facts, names, numbers and meaning; no automatic substring truncation.
- No publication, paid generation, schedule changes or old autopilot activation.
- Existing approved wording requires owner permission for semantic edits; this request permits preparing compact future drafts before their review.
- Chat attachments cannot be intercepted by repository code: document mandatory CLI use and do not claim platform-wide enforcement.

## Root cause evidence
The four Ryanair paragraphs each measured three lines at pinned Almarai Bold 44 and 908px wrapping width. The assistant displayed them without running the renderer. fixed_information_template.render validates only during rendering. Legacy autopilot agent prompts allow body<=320 while policy SNAP_BODY_MAX=130; neither models this four-bullet master and neither should silently become the new template authority.

## Review Focus
- Equal character counts can have different Arabic glyph widths: line measurement wins.
- Long words, empty paragraphs and unsupported controls must fail clearly, without a partial display-ready card.
- Changed wording, fonts or settings invalidate an earlier measurement receipt.
- Mixed Arabic/Latin digits and punctuation must match renderer wrapping exactly.
- Shared-helper extraction must preserve existing raster output and challenge behavior.

## Task 1: Shared geometry and pre-display draft gate
**Files:** Create publishing_v2/information_text_fit.py and tests/test_information_text_fit.py; modify publishing_v2/fixed_information_template.py and tests/test_fixed_information_template.py.
**Interfaces:** measure_card(draft: dict) -> dict with per-role text, character count (including spaces/punctuation), line strings/counts, actual ink bounds, fit status and violations; prepare_text(draft: dict) -> dict with exact display text plus text/settings/font hashes only when fit. CLI consumes JSON headline/bullets/closing and returns nonzero on overflow. Existing rendering consumes shared wrapping rather than a second implementation.
- [ ] Write failing regressions: original Ryanair bullets rejected as three lines; concise versions accepted as two; title/closing overflow; 0 or >4 bullets; oversized token; blank text; mixed Arabic/Latin; same-length wide/narrow strings; receipt invalidation after text/settings change. No mocks for font measurement.
- [ ] Run tests and confirm expected missing-feature failure.
- [ ] Extract exact current measurement logic without visual changes. Derive geometry and fonts from current master; count raw characters separately from renderer-normalized text. Return per-paragraph remaining pixel/line capacity rather than inventing a single maximum character count. Reject invisible/control-only input safely.
- [ ] Add draft CLI which emits display-ready text only on success. Overflow response supplies diagnostics for internal rewriting, not a publicly reviewable draft. No summarization model or literal text chopping.
- [ ] Test renderer/CLI parity and unchanged pixels for existing fixed-template fixtures; verify challenge tests remain unchanged.

## Task 2: Mandatory authoring entry point and verification
**Files:** Modify AGENTS.md; create docs/information-text-drafts.md; add a Ryanair regression fixture under tests/fixtures/ (not approved/).
- [ ] Document the single workflow for morning/evening/Saudi/story text in chat: draft privately -> measure -> revise privately -> remeasure -> display exact passing output. Re-run after every user edit. Current challenge flow unchanged.
- [ ] Do not connect retired autopilot schemas or start old schedules. Map any genuinely live automated information writer before integration; unknown consumers remain unchanged and explicitly reported.
- [ ] Verify counts and line results on shortened Ryanair text without producing/publishing a design.
- [ ] Run focused tests then full pytest in an isolated copy because tests can write state. Record all failures by name and distinguish baseline from regressions.
- [ ] Review diff, inspect push triggers, preserve concurrent changes, and persist tested changes through authorized expected-SHA GitHub update; no force and no publish-request modification.

## Checkpoint
Diagnosis and plan only. No production code changed yet. Pending owner plan confirmation and native execution selection under the planning skill.
