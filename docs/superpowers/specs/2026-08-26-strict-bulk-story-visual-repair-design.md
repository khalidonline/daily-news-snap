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
- aliases, person/entity metadata, subject key, and logo identity/domain
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
5. update local files, `images/images.txt`, `images/relevance.json`, story identity metadata, and logo index data only for accepted candidates;
6. rebuild runtime coverage after each batch;
7. stop only at 123/123 PASS or when a full pass makes zero safe changes;
8. emit a structured unresolved report for any remaining stories.

The orchestrator is resumable and idempotent. Re-running it must skip already-satisfied stories and must not redownload or duplicate accepted assets.

### 2. Canonical logo identity resolution

Logo repair runs before photo sourcing because it is cheap and low-risk.

The accepted logo identity for a story is an explicit editorial association, never a loose keyword guess. Resolution order is:

1. existing `logo:` declaration in `stories.txt`;
2. exact existing association in `images/logos/index.json` for a declared story entity/alias;
3. an exact canonical organization/product/brand that is central to the story and can be verified from authoritative source metadata.

When rule 3 is needed, the pipeline may add an explicit `logo:` identity to the story only when one canonical identity is defensible and unambiguous. Examples of acceptable relationships include a company story's own mark, a founder biography's central company when the story is specifically about founding/building/returning to that company, or a product/topic with a canonical official mark. A merely adjacent employer, sponsor, investor, city business, or generic institution is not enough.

For topic/history/place stories with no company, the pipeline may use an official institutional or product identity only when it is directly central to the story and would be editorially understandable without explanation. If multiple plausible marks exist or the relationship is contextual rather than central, the story remains `LOGO_IDENTITY_MISSING` until the source resolver can establish a stronger canonical identity; it does not receive an arbitrary logo.

For each `NEEDS LOGO` story, the pipeline first inspects existing local logos. If one local file is unambiguously tied to the accepted identity, it adds the missing index/story association without downloading anything.

If no local logo is usable, the pipeline may fetch a logo only for the accepted explicit identity/domain. The saved file must live under `images/logos/`, decode locally, and be indexed under that identity. The system must never derive a logo domain from a generic image-search term.

### 3. Candidate photo sourcing

Photo repair works from each story's exact deficit (1–4 photos). Candidate discovery is source-tiered and stops once enough accepted, distinct photos exist.

Preferred order:

1. existing local library files not yet counted, if they have reviewable provenance and an exact story/entity match;
2. Wikimedia Commons / other sources with machine-readable reuse metadata;
3. Library of Congress or comparable public institutional archives;
4. Openverse results with explicit source/license metadata;
5. exact first-party company/government/institution media pages when the image is directly relevant and the source URL/credit can be recorded.

First-party images are allowed as sourced editorial assets with provenance; the pipeline must not label them open-license unless the source explicitly says so.

Generic web image search is not an approval source. A search result can help discovery, but the accepted asset must resolve to a traceable source page or direct first-party/institutional media URL.

### 4. Story-aware sourcing beats

Candidate queries are derived from the story metadata and editorial structure, not just the first noun in the title.

For company stories, the source planner should prefer a sequence such as founder/origin, early operation/product, turning point, and later/modern result.

For biography stories, it should prefer exact person, early work, invention/company/product, and legacy/context.

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
- source metadata establishes the intended subject/context;
- automated relevance review does not contradict that source metadata;
- the resulting verdict is `DIRECT` or `STRONG_CONTEXT`.

`WEAK_GENERIC` and `WRONG_ENTITY` never count.

For person stories, exact identity is mandatory but is established from trustworthy source metadata, not facial recognition. The source page/file caption/title/structured metadata must explicitly identify the exact person. The image relevance model may reject an obvious mismatch or unsuitable image, but model face recognition is never used as the sole proof of identity. If the source metadata does not explicitly identify the person, reject the candidate.

For non-person assets, authoritative captions/descriptions and exact entity/source-page context provide the primary identity evidence. The automated relevance reviewer returns a structured decision containing `verdict` (`DIRECT`, `STRONG_CONTEXT`, `WEAK_GENERIC`, `WRONG_ENTITY`), a short reason, and whether the source metadata is sufficient. Missing/invalid/ambiguous model output fails closed.

A transient model/API failure is not an approval; the candidate remains unreviewed and does not count.

### 6. Asset registration

Accepted photos are saved as stable local files under `images/` with deterministic, collision-resistant names based on story slug / subject / source beat. `images/images.txt` receives tags and credit. `images/relevance.json` receives the exact story verdict, source URL, source title/caption where available, and validation reason.

The pipeline must preserve existing curated relevance entries. It must never rebuild the ledger in a way that erases hand-curated non-`rt-*` verdicts such as the Jack Bogle repairs.

Accepted logos are saved under `images/logos/` and indexed by exact accepted identity/domain. When the pipeline adds a new canonical logo identity to a story, that mapping is committed as explicit story metadata so future runtime runs do not need to rediscover it.

### 7. Batch size and commit strategy

One workflow run may repair many stories, but writes are committed in bounded batches so progress survives timeouts or external-source failures.

Default batch target is 15 stories, configurable by an environment/input value. A batch may end earlier if it reaches a configured asset cap or runtime deadline.

After each batch:

1. run the local runtime coverage board;
2. run relevance/dedupe tests;
3. commit only if coverage or validated assets changed;
4. continue from the new board.

A source outage for one story must not abort unrelated repairs. The pipeline records the story/source error and continues.

### 8. GitHub Actions workflow

Add `.github/workflows/bulk-visual-repair.yml` with manual dispatch. Inputs are limited to safe operational controls such as batch size and maximum passes; they must not include switches that weaken relevance, dedupe, or runtime thresholds.

The workflow will:

- check out the explicitly dispatched repair branch;
- install dependencies;
- run the bulk repair orchestrator;
- run the runtime/relevance test suite;
- rebuild and upload the full coverage/review artifact;
- commit validated asset/ledger/index/story-metadata changes in bounded batches;
- expose a final summary with PASS count and unresolved stories.

The workflow is safe to rerun after GitHub `startup_failure`: no duplicate assets, duplicate index lines, or destructive ledger rewrites.

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

If a full automated pass makes zero safe changes while PASS is below 123, the workflow exits non-zero with the unresolved report. Implementation then improves source adapters or explicit canonical identity rules for those unresolved classes; it does not relax acceptance criteria.

### 10. Renderer verification

The production runtime contract already enforces that a PASS story's approved photo pool is consumed by the renderer. The bulk project will retain and expand automated regression tests for that behavior.

We will not require 123 manual renders. Instead, after 123/123 runtime PASS, run a representative end-to-end sample across story types: at minimum one company story, one biography, one Saudi company/person story, one historical/topic story, and one place/travel story. Inspect all six frames for each sampled story.

The sample is a renderer sanity check, while the authoritative catalogue completion metric remains 123/123 runtime PASS plus renderer-contract tests. If a sampled render reveals a new class of renderer bug, fix the renderer contract and add a regression before declaring the catalogue finished.

## Failure handling

The pipeline distinguishes:

- `SOURCE_UNAVAILABLE`: candidate host/API unavailable;
- `NO_SAFE_CANDIDATE`: searches exhausted without a defensible relevant image;
- `IDENTITY_UNPROVEN`: person/entity identity cannot be established from source metadata;
- `DUPLICATE_ONLY`: candidates duplicate already-counted visuals;
- `LOGO_IDENTITY_MISSING`: no defensible canonical logo identity/domain exists;
- `VALIDATION_ERROR`: decode/dimension/relevance validation failed;
- `EXTERNAL_API_ERROR`: temporary model/source API failure.

These states do not become PASS. They are written to the unresolved artifact with attempted sources and reasons so a later retry can continue intelligently.

## Tests

Implementation follows TDD for new behavior. Tests cover at minimum:

- backlog ordering and deficit computation from runtime coverage;
- idempotent reruns;
- deterministic existing-logo association;
- canonical-logo resolver accepts a unique central identity and refuses ambiguous/context-only identities;
- refusal to infer logo domains from loose search keywords;
- candidate SHA/dHash duplicate rejection;
- rejection of `WEAK_GENERIC` / `WRONG_ENTITY` / unreviewed assets;
- exact-person identity requires explicit source metadata and fails closed without it;
- preservation of existing relevance ledger entries;
- batch continuation after one story/source fails;
- zero-progress exit below 123/123;
- final 123/123 completion assertion against a generated board;
- renderer contract still places four distinct approved photos while preserving a relevant logo.

## Rollout

Phase 1: implement orchestrator skeleton, board generation, canonical logo repair, idempotency, and tests.

Phase 2: add tiered photo discovery + strict validation + provenance recording.

Phase 3: run bulk workflow repeatedly until no automatic safe progress remains; improve source adapters or canonical identity resolution only for unresolved classes, without weakening acceptance rules.

Phase 4: reach a fresh 123/123 authoritative runtime board, then run representative end-to-end renders and inspect artifacts.

PR #2 remains draft and must not merge until the final completion gate and renderer sanity sample pass.
