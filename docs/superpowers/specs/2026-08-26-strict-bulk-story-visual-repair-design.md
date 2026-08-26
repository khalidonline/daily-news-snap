# Strict Bulk Story Visual Repair — Design

Date: 2026-08-26
Status: Proposed for implementation
Branch: `repair/story-visual-coverage`
PR: #2

## Goal

Bring the entire Story Bot catalogue to the existing runtime truth standard without weakening the gate and without requiring one manual repair/render loop per story.

A story is complete only when the authoritative runtime sees:

- 4 distinct, relevant, usable local photos; and
- 1 relevant local logo.

The bulk repair system must preserve the current fail-closed semantics. It may improve sourcing and association, but it must not make weak, generic, duplicate, wrong-entity, remote-only, missing, undecodable, or unreviewed assets count.

## Non-goals

This project does not lower the 4-photo + logo requirement, mass-approve existing `rt-*` files, make remote URLs count at runtime, or globally relax Story Bot's image relevance rules. It also does not require 123 individual Story-to-Snapchat renders as the completion mechanism.

## Source of truth

The repair pipeline will call the same runtime-facing functions used by production, centered on `story_runtime.approved_runtime_visuals()` / `coverage()` and `runtime_relevance.asset_countable()`. A separate repair score must never disagree with runtime PASS/FAIL.

Every batch begins by rebuilding a machine-readable board for all stories with:

- story text / exact key
- aliases, person/entity metadata, subject key, and logo domain
- approved photo filenames
- approved logo filenames
- missing-photo count
- missing-logo flag
- runtime status

The board is regenerated after every repair pass and is the sole backlog for the next pass.

## Architecture

### 1. `tools/bulk_visual_repair.py` — orchestrator

A new orchestration script will process the complete story catalogue in deterministic passes rather than story-by-story manual sessions.

It will:

1. load every story and current runtime coverage;
2. repair deterministic metadata/logo gaps first;
3. repair photo gaps in bounded batches;
4. validate every candidate before registration;
5. update local files, `images/images.txt`, `images/relevance.json`, and logo index data only for accepted candidates;
6. rebuild runtime coverage after each batch;
7. stop only at 123/123 PASS or when no safe progress is possible;
8. emit a structured unresolved report for any remaining stories.

The orchestrator is resumable and idempotent. Re-running it must skip already-satisfied stories and must not redownload or duplicate accepted assets.

### 2. Deterministic logo repair

Logo repair runs before photo sourcing because it is cheap and low-risk.

For each `NEEDS LOGO` story, the pipeline will first inspect existing story metadata and `images/logos/index.json` for a unique exact company/entity association. If one existing local logo is unambiguously tied to the story subject, the pipeline may add the missing alias/domain association without downloading anything.

If no local logo is usable, the pipeline may fetch a logo only when the story has an explicitly declared company identity / logo domain. The saved file must live under `images/logos/`, decode locally, and be indexed under the declared domain. The system must never infer a logo domain from a loose search keyword.

Stories with no defensible company/entity logo identity remain unresolved rather than receiving a guessed mark.

### 3. Candidate photo sourcing

Photo repair works from each story's exact deficit (1–4 photos). Candidate discovery is source-tiered and stops once enough accepted, distinct photos exist.

Preferred order:

1. existing local library files not yet counted, if they have a reviewable provenance and exact story/entity match;
2. Wikimedia Commons / other sources with machine-readable reuse metadata;
3. Library of Congress or comparable public institutional archives;
4. Openverse results with explicit source/license metadata;
5. exact first-party company/government/institution media pages when the image is directly relevant and the source URL/credit can be recorded.

First-party images are allowed as sourced editorial assets with provenance; the pipeline must not label them open-license unless the source explicitly says so.

Generic web image search is not an approval source. A search result can help discovery, but the accepted asset must resolve to a traceable source page or direct first-party/institutional media URL.

### 4. Story-aware sourcing beats

Candidate queries are derived from the story metadata and editorial structure, not just the first noun in the title.

For company stories, the source planner should prefer a sequence such as founder/origin, early operation/product, turning point, and later/modern result.

For biography stories, it should prefer exact person identity, early work, invention/company/product, and legacy/context.

For place/history/topic stories, it should prefer distinct visual beats that directly document the subject rather than four near-identical establishing shots.

The planner may generate more candidates than needed, but acceptance remains per-asset and fail-closed.

### 5. Strict candidate validation

A candidate is registered only after all of the following pass:

- local download succeeds;
- image decodes with Pillow;
- minimum usable dimensions are met;
- exact SHA is not already present;
- perceptual dHash is not within the existing duplicate threshold of another counted image;
- the file is not a logo/flat graphic being smuggled into the photo pool;
- exact story/person/entity relevance is confirmed;
- the resulting verdict is `DIRECT` or `STRONG_CONTEXT`.

`WEAK_GENERIC` and `WRONG_ENTITY` never count.

For person stories, exact identity is mandatory. If identity cannot be established confidently, reject the candidate.

The automated relevance decision should reuse the project's existing vision/relevance machinery where possible and record a reason and source metadata for every accepted/rejected candidate. A transient model/API failure is not an approval; the candidate remains unreviewed and does not count.

### 6. Asset registration

Accepted photos are saved as stable local files under `images/` with deterministic, collision-resistant names based on story slug / subject / source beat. `images/images.txt` receives tags and credit. `images/relevance.json` receives the exact story verdict and source URL.

The pipeline must preserve existing curated relevance entries. It must never rebuild the ledger in a way that erases hand-curated non-`rt-*` verdicts such as the Jack Bogle repairs.

Accepted logos are saved under `images/logos/` and indexed by exact declared identity/domain.

### 7. Batch size and commit strategy

One workflow run may repair many stories, but writes are committed in bounded batches so progress survives timeouts or external-source failures.

Default batch target: 10–20 stories or a comparable asset-count cap per commit.

After each batch:

1. run the local runtime coverage board;
2. run relevance/dedupe tests;
3. commit only if coverage or validated assets changed;
4. continue from the new board.

A source outage for one story must not abort unrelated repairs. The pipeline records the story/source error and continues.

### 8. GitHub Actions workflow

Add a workflow such as `.github/workflows/bulk-visual-repair.yml` with manual dispatch and optional bounded repeat mode.

The workflow will:

- check out `repair/story-visual-coverage` (or the explicitly dispatched branch);
- install dependencies;
- run the bulk repair orchestrator;
- run the runtime/relevance test suite;
- rebuild and upload the full coverage/review artifact;
- commit validated asset/ledger/index changes in bounded batches;
- expose a final summary with PASS count and unresolved stories.

The workflow must be safe to rerun after GitHub `startup_failure`: no duplicate assets, duplicate index lines, or destructive ledger rewrites.

### 9. Completion gate

The catalogue is complete only when a fresh authoritative board reports:

- total stories: 123;
- PASS: 123;
- every PASS story has at least 4 runtime-approved local photos;
- every PASS story has at least 1 runtime-resolved local logo;
- all counted files exist and decode;
- all counted photos are exact/perceptually distinct under current thresholds;
- all counted photo verdicts are `DIRECT` or `STRONG_CONTEXT`;
- unreviewed `rt-*`, `WEAK_GENERIC`, and `WRONG_ENTITY` assets contribute zero coverage.

A green workflow alone is insufficient if the final board is below 123/123.

### 10. Renderer verification

The production runtime contract already enforces that a PASS story's approved photo pool is consumed by the renderer. The bulk project will retain and expand automated regression tests for that behavior.

We will not require 123 manual renders. Instead, after 123/123 runtime PASS, run a representative end-to-end sample across story types (for example: company, biography, Saudi company/person, historical topic, place/travel) and inspect their six-frame artifacts. The sample is a renderer sanity check, while the authoritative catalogue completion metric remains 123/123 runtime PASS plus renderer-contract tests.

If a sampled render reveals a new class of renderer bug, fix the renderer contract and add a regression before declaring the catalogue finished.

## Failure handling

The pipeline distinguishes:

- `SOURCE_UNAVAILABLE`: candidate host/API unavailable;
- `NO_SAFE_CANDIDATE`: searches exhausted without a defensible relevant image;
- `IDENTITY_UNPROVEN`: person/entity identity cannot be verified;
- `DUPLICATE_ONLY`: candidates duplicate already-counted visuals;
- `LOGO_IDENTITY_MISSING`: no defensible logo entity/domain exists;
- `VALIDATION_ERROR`: decode/dimension/relevance validation failed;
- `EXTERNAL_API_ERROR`: temporary model/source API failure.

These states do not become PASS. They are written to the unresolved artifact with attempted sources and reasons so a later retry can continue intelligently.

## Tests

Implementation follows TDD for new behavior. Tests should cover at minimum:

- backlog ordering and deficit computation from runtime coverage;
- idempotent reruns;
- deterministic existing-logo association;
- refusal to guess logo domains;
- candidate SHA/dHash duplicate rejection;
- rejection of `WEAK_GENERIC` / `WRONG_ENTITY` / unreviewed assets;
- exact-person identity fail-closed behavior;
- preservation of existing relevance ledger entries;
- batch continuation after one story/source fails;
- final 123/123 completion assertion against a generated board;
- renderer contract still places four distinct approved photos while preserving a relevant logo.

## Rollout

Phase 1: implement orchestrator skeleton, board generation, deterministic logo repairs, idempotency, and tests.

Phase 2: add tiered photo discovery + strict validation + provenance recording.

Phase 3: run bulk workflow repeatedly until no automatic safe progress remains; improve source adapters only for unresolved classes, without weakening acceptance rules.

Phase 4: reach a fresh 123/123 authoritative runtime board, then run representative end-to-end renders and inspect artifacts.

PR #2 remains draft and must not merge until the final completion gate and renderer sanity sample pass.
