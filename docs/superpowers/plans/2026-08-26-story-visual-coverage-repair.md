# Story Visual Coverage Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every story to runtime PASS using 4 distinct, approved, relevant local photos plus 1 relevant local logo.

**Architecture:** Keep the runtime relevance gate unchanged. First review and classify existing materialized `rt-*` assets story-by-story, then source only the remaining gaps from open-license or official sources. Every accepted asset is local, decodable, deduplicated, credited in `images/images.txt`, and marked `DIRECT` or `STRONG_CONTEXT` in `images/relevance.json` when it is an `rt-*` materialization or otherwise needs an explicit ruling.

**Tech Stack:** Python 3.12, Pillow, existing `story_runtime.py`, `runtime_relevance.py`, `image_precheck.py`, GitHub Actions, Wikimedia Commons / official company or government sources.

**Spec:** Runtime gate merged in PR #1: 4 distinct approved relevant photos + 1 local logo; unreviewed `rt-*` assets fail closed.

## Global Constraints

- Never weaken the 4 photos + 1 logo runtime gate.
- Only `DIRECT` and `STRONG_CONTEXT` assets count.
- `WEAK_GENERIC` and `WRONG_ENTITY` never count.
- Unreviewed `rt-*` assets fail closed.
- Exact and perceptual duplicates count once.
- Prefer Wikimedia Commons/public-domain/CC sources; official company/government sources are acceptable with source/rights notes.
- Do not seed editorial-copyright images unless reuse is explicitly cleared.
- Do not use generic filler merely to raise counts.

---

### Task 1: Generate a reviewable runtime inventory

**Files:**
- Create: `tools/build_runtime_review.py`
- Create: `.github/workflows/runtime-review.yml`

**Interfaces:**
- Consumes: `stories.txt`, `images/images.txt`, `images/relevance.json`, `story_runtime.approved_runtime_visuals()`
- Produces: `out/runtime-review/status.csv`, `out/runtime-review/materialized.csv`, contact sheets for `rt-*` assets, and a GitHub Actions artifact.

- [ ] Add a report script that maps every local asset to candidate story lines using the same runtime matcher.
- [ ] Render numbered contact sheets containing the image plus filename and story label.
- [ ] Emit current PASS/failure status for all 123 stories.
- [ ] Add a PR workflow that runs the report and uploads the artifact.
- [ ] Verify the artifact is generated in GitHub Actions.

### Task 2: Repair Jack Bogle to PASS

**Files:**
- Modify: `images/images.txt`
- Modify: `images/relevance.json`
- Add: `images/<bogle-vanguard-assets>.jpg`

**Interfaces:**
- Consumes: existing `jack-bogle.jpg`, Vanguard logo, official/open-license Bogle/Vanguard/index-fund sources.
- Produces: 4 distinct relevant local photos + Vanguard logo.

- [ ] Confirm the existing Bogle portrait and reject the generic Edison ticker.
- [ ] Source three distinct Bogle/Vanguard/index-fund-specific photographic or documentary visuals that genuinely explain the story.
- [ ] Add the files locally with explicit credits.
- [ ] Mark each new asset `DIRECT` or `STRONG_CONTEXT` where required.
- [ ] Run the runtime review and confirm Jack Bogle is PASS.

### Task 3: Review all existing materialized assets

**Files:**
- Modify: `images/relevance.json`
- Modify as needed: `images/images.txt`

**Interfaces:**
- Consumes: Task 1 contact sheets and materialized-asset report.
- Produces: one explicit relevance verdict for every `rt-*` asset/story association.

- [ ] Visually review every unreviewed materialized asset.
- [ ] Assign `DIRECT`, `STRONG_CONTEXT`, `WEAK_GENERIC`, or `WRONG_ENTITY` per story.
- [ ] Remove/veto obviously wrong aliases or tags when necessary.
- [ ] Rerun runtime status and record the new board.

### Task 4: Close cheap gaps first

**Files:**
- Modify: `images/logos/*`, `images/logos/index.json`, `images/images.txt`, `images/relevance.json`
- Add: missing local photo/logo files.

**Interfaces:**
- Consumes: runtime failure queue sorted by smallest gap.
- Produces: PASS stories.

- [ ] Resolve stories missing only a logo using the declared/verified entity identity.
- [ ] Resolve stories needing one photo.
- [ ] Resolve stories needing two photos.
- [ ] Rerun the audit after each batch.

### Task 5: Close larger remaining gaps

**Files:**
- Modify/add the same asset/index/ledger files as Task 4.

**Interfaces:**
- Consumes: remaining runtime repair queue.
- Produces: all 123 stories at PASS or a documented blocker requiring owner-provided/private archival material.

- [ ] Source direct narrative beats for stories needing 3–4 photos.
- [ ] Prefer origin/person/place/product/turning-point/result coverage over repeated portraits.
- [ ] Verify source and license/rights status before seeding.
- [ ] Rerun runtime status until the queue is empty or only truly non-public archival blockers remain.

### Task 6: Final runtime verification

**Files:**
- No production changes unless a test exposes a bug.

**Interfaces:**
- Consumes: repaired library.
- Produces: final acceptance report.

- [ ] Run runtime status for all 123 stories.
- [ ] Assert every PASS story has >=4 distinct approved photos and >=1 logo.
- [ ] Run five representative dry-run decks, including Jack Bogle.
- [ ] Report exact filenames selected per frame and any unused approved assets.
- [ ] Merge only after CI and runtime verification succeed.
