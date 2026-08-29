# Cost-Controlled Story-to-Snapchat Operation Model

Date: 2026-08-29
Status: Design approved in chat; pending user review of this written spec

## Problem

The current Story-to-Snapchat workflow can repeat expensive editorial model work when the operator only intends to rerender or repair visuals. A GitHub rerun enters `ready_story_publish.py`, then `story_runtime.py`, then the normal Story Bot research/generation path with `STORY_MODEL=claude-opus-5`. This makes one operational action capable of creating multiple distinct paid Claude messages for the same story.

Riyadh also demonstrated a second operational problem: visual defects are often frame-specific, but the current workflow can rerun the whole story. That increases cost, latency, and operator review volume without improving the already-approved editorial brief.

## Goals

1. Limit expensive editorial generation to **one paid model call per story revision** by default.
2. Make ordinary reruns and visual repairs reuse a persisted editorial brief and require **zero editorial-model calls**.
3. Repair only failed visual slots instead of regenerating the story.
4. Record every editorial-model call with enough metadata to audit cost and diagnose unexpected charges.
5. Fail closed when cache or budget state is ambiguous; never silently spend again.
6. Reduce operator review to final READY/REVIEW candidates, not intermediate repair attempts.
7. Preserve current publication quality and existing relevance/quality gates.

## Non-goals

- Replacing the current editorial model solely to reduce cost.
- Weakening photo relevance, city/era, dust/haze, or strict runtime gates.
- Rewriting the whole Story Bot in this change.
- Building a general billing platform.
- Automatically publishing a story that fails existing publication gates.

## Approaches considered

### A. Cache-only patch at the workflow boundary

Store the last rendered result and skip the workflow when it exists.

**Pros:** smallest implementation.

**Cons:** too coarse. It does not separate editorial generation from visual repair, makes prompt/version changes hard to reason about, and does not provide a reliable model-call audit trail.

### B. Split editorial brief from visual assembly — selected

Persist the expensive editorial brief as a versioned artifact. Renders and visual repairs consume that brief without calling the editorial model. Add a call guard and usage ledger around the one uncached editorial call.

**Pros:** preserves quality, makes reruns cheap, isolates visual repair, produces a clean operating model, and directly prevents the multiple-paid-call pattern.

**Cons:** touches several existing boundaries and requires a small state model.

### C. Replace Opus with a cheaper model everywhere

**Pros:** lower unit cost.

**Cons:** does not solve repeated-call waste and could reduce editorial quality. It can be evaluated later using measured pilot data, but it is not the primary control.

## Architecture

### 1. Versioned editorial brief store

Add a focused module such as `story_brief_store.py`.

Persist final model output under:

`state/story_briefs/<story-id>/<revision-key>.json`

The revision key is content-addressed from:

- normalized story identity,
- active editorial system prompt content,
- story-specific editorial prompt additions active at research time,
- model name,
- frame count,
- a small explicit schema/version constant.

Hashing the actual active prompt is preferred to a manually maintained prompt version because wrappers such as Story Focus can extend the prompt at runtime. A schema version remains available for deliberate invalidation when the cached JSON contract changes.

The cached payload contains:

- story identity,
- revision key,
- model,
- generation timestamp,
- complete parsed editorial brief returned by research,
- response/message ID when available,
- input/output token usage when available,
- source/search metadata already present in the brief,
- prompt hash and brief schema version.

The cache is written atomically (`.tmp` then rename) only after parsing and validation succeed.

### 2. Cached research wrapper

Split the existing research path conceptually into:

- `_research_uncached(story)` — existing paid model behavior,
- `research(story)` — cache/budget wrapper.

Behavior:

1. Compute the revision key from the active prompt and model configuration.
2. If a valid cached brief exists, return it immediately and log `EDITORIAL_CACHE_HIT`.
3. If mode is visual-only and no valid cache exists, stop with a clear error. Do not call Claude.
4. If cache is missing in normal auto mode, reserve the one allowed editorial call and invoke `_research_uncached` once.
5. Validate and persist the result, then return it.
6. Do not automatically retry an expensive editorial call in the same operation.

Post-research deterministic transformations such as city closing normalization may continue to run on every render. This lets visual/editorial policy code improve without spending again, while any true prompt change naturally changes the prompt hash and creates a new revision key.

### 3. Hard editorial-call guard

Add a small module such as `story_cost_guard.py`.

Default policy:

- `MAX_EDITORIAL_CALLS_PER_REVISION=1`
- visual repair mode permits `0` editorial calls,
- a second paid editorial generation for the same revision is blocked,
- cache corruption is a block, not permission to regenerate,
- explicit regeneration requires an operator-controlled override.

The guard is primarily call-count based because it remains reliable even when exact model pricing changes or a model's rate is not configured.

Optional dollar budgets can be layered on top once pricing is configured:

- `STORY_MAX_ESTIMATED_USD`
- input/output USD per million tokens by model from configuration.

A missing price must never disable the call-count guard.

### 4. Usage ledger

Add append-only state, for example:

`state/model_usage.jsonl`

Record one row for each editorial model attempt/result:

- UTC timestamp,
- GitHub workflow run ID and attempt when present,
- story ID,
- revision key,
- purpose (`editorial_generation`, `forced_regeneration`),
- model,
- response/message ID when available,
- input tokens,
- output tokens,
- estimated USD when pricing is configured,
- result status,
- cache hit flag where useful.

The ledger is diagnostic and auditable. The hard guard must not depend solely on successful ledger append.

### 5. Explicit operating modes

Use one simple mode variable, e.g. `STORY_OPERATION_MODE`:

- `auto` — default. Reuse cache; generate once only if no valid revision exists.
- `visual_only` — require cached editorial brief; model calls are forbidden.
- `regenerate_editorial` — explicit operator override to create a new editorial revision. This is never selected by an ordinary rerun.

GitHub workflow dispatch should expose the override intentionally rather than making rerun equivalent to regenerate.

Scheduled production remains `auto`: a truly new story can generate once; an existing revision becomes a cache hit.

### 6. Frame-only visual repair

Editorial brief and visual state are separate.

A visual repair run receives the locked brief and a set of failed frame indices or derives them from the current frame-level QA state. It may:

- search or select replacement assets only for failed frames,
- rerender affected frames or the final deck,
- reuse all approved frame text,
- reuse already-approved images for untouched frames,
- run deterministic visual gates,
- never call the editorial model.

A bad image therefore creates a visual repair task, not an editorial regeneration.

### 7. Story/deck states

Use explicit operational states:

- `EDITORIAL_MISSING`
- `EDITORIAL_LOCKED`
- `VISUAL_ASSEMBLY`
- `BLOCKED`
- `REVIEW`
- `READY`

A story cannot be `READY` merely because the technical runtime photo count passes. Existing frame relevance and photo-quality rules remain authoritative, and deck-level publication checks may raise REVIEW/BLOCKED.

### 8. Telegram operation

Intermediate repair attempts should not repeatedly notify the operator.

Default behavior:

- no Telegram album for internal `visual_only` repair attempts,
- send when the deck reaches `READY`,
- send once for `REVIEW` when operator judgment is genuinely required,
- suppress duplicate notifications for an unchanged rendered deck hash.

Persist a small notification ledger keyed by story revision + rendered deck hash so rerunning an identical result does not resend it.

Dry-run artifacts remain available in GitHub Actions even when Telegram is suppressed.

## Data flow

### New story

`story selected`
→ compute editorial revision key
→ cache miss
→ guard reserves one editorial call
→ Claude research/generation once
→ validate + persist brief
→ `EDITORIAL_LOCKED`
→ visual assembly
→ frame/deck QA
→ READY / REVIEW / BLOCKED

### Ordinary GitHub rerun

`same story + same prompt/model revision`
→ cache hit
→ zero editorial calls
→ visual assembly/rerender only
→ READY / REVIEW / BLOCKED

### Visual repair

`locked brief + failed frames`
→ `visual_only`
→ zero editorial calls allowed
→ repair only failed visual slots
→ rerender/QA
→ READY / REVIEW / BLOCKED

### Intentional rewrite

operator chooses explicit `regenerate_editorial`
→ new revision/override path
→ one new paid call
→ persist separately
→ prior revision remains auditable

## Failure behavior

- **Missing cache in `visual_only`:** stop; do not spend.
- **Malformed/corrupt cache:** stop and report cache problem; do not silently regenerate.
- **Paid model call HTTP/model failure:** record failure if possible and stop; no automatic Opus retry.
- **Model response fails parse/validation:** keep failure evidence and stop; regeneration requires explicit operator action.
- **Usage ledger write failure:** warn/block according to implementation safety, but never use it as a reason to allow another call.
- **Pinned/approved visual unavailable:** follow existing visual fail-closed rules; do not regenerate editorial text.
- **Telegram failure:** do not change READY/BLOCKED editorial state and do not trigger a model retry.

## Persistence

The repository already uses `state/` files and GitHub Actions checks out a persistent repair branch. The first implementation should follow that existing pattern and persist story briefs/ledgers in repository state, with existing commit/push helpers where appropriate.

No secrets, API keys, raw authorization headers, or private account data may be written to these files.

If repository-state contention becomes a real problem during the pilot, move only the persistence mechanism later; do not complicate the first implementation preemptively.

## Workflow changes

Update `.github/workflows/story.yml` so:

- default operation is `auto`,
- an explicit dispatch input can request `visual_only`,
- editorial regeneration is a separate explicit input/action,
- ordinary workflow rerun does not set regeneration,
- cost/usage identifiers include `GITHUB_RUN_ID` and `GITHUB_RUN_ATTEMPT`,
- internal repair runs can suppress Telegram,
- `POST_TO_SNAPCHAT` behavior is unchanged.

The existing concurrency group is retained.

## Testing

### Unit tests

1. Cache miss performs exactly one mocked editorial call and persists a valid brief.
2. Cache hit performs zero editorial calls.
3. Repeating the same story/revision performs zero additional calls.
4. `visual_only` with a valid cache performs zero calls.
5. `visual_only` with missing cache fails before any model call.
6. Corrupt cache fails closed and does not regenerate.
7. A second editorial call reservation for one revision is blocked.
8. Explicit regeneration uses a separate allowed path and is auditable.
9. Message ID/token usage are written to the ledger when exposed by the response.
10. Missing pricing still enforces call-count limits.
11. Frame-only repair preserves editorial text and untouched visual slots.
12. Telegram dedupe suppresses the same deck hash and allows a changed READY/REVIEW deck.

### Workflow regression tests

- Normal rerun maps to `auto`, never implicit regeneration.
- Visual-only dispatch maps to `visual_only`.
- Regeneration requires the explicit override.
- Snapchat posting remains disabled in dry-run mode.

### Existing suites

All current runtime relevance, city specificity, photo quality, publishing, compile, and precheck suites must remain green.

## Rollout

### Phase 1 — cost safety

Implement brief cache, revision key, hard call guard, usage ledger, and workflow modes. Do not intentionally change story output.

Acceptance criterion: rerunning the same story revision produces `EDITORIAL_CACHE_HIT` and no editorial model call.

### Phase 2 — repair operation

Implement frame-only visual repair and Telegram final-only/deduped notification behavior.

Acceptance criterion: a visual defect can be repaired and rerendered without any editorial model call or repeated Telegram spam.

### Phase 3 — representative pilot

Run approximately 10 diverse stories covering:

- Saudi company,
- international company,
- Saudi person,
- international person,
- city,
- historical event,
- finance,
- technology,
- government/institution,
- consumer/business story.

Track:

- expensive editorial calls per story revision,
- cache-hit rate on reruns,
- estimated cost where pricing is configured,
- first-pass READY rate,
- visual repairs per story,
- human REVIEW rate.

Do not process the full backlog until the pilot shows the operating model is stable.

## Success criteria

1. **≤ 1 expensive editorial call per story revision by default.**
2. **0 editorial calls for ordinary reruns of an existing revision.**
3. **0 editorial calls for normal visual repair.**
4. Every paid editorial call has an auditable message/run/story/revision record when the API exposes those fields.
5. No automatic paid retry after a failed/corrupt run.
6. Existing publication-quality gates remain at least as strict as before.
7. Operator receives only final READY or genuine REVIEW candidates, not repeated intermediate repair decks.
8. A 10-story pilot demonstrates the above before broad backlog execution.

## Operational rule

A GitHub workflow rerun is a request to **reuse and rerender**, not a request to **repurchase the editorial generation**.

Only an explicit editorial-regeneration action may authorize another expensive model call for an already-generated story revision.
