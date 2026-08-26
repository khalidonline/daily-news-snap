# Bulk visual repair runner redesign

Date: 2026-08-26
Status: approved direction, implementation pending

## Problem

The current bulk visual repair workflow can spend an unbounded amount of wall-clock time scanning unresolved stories after a zero-progress batch. The fallback loop probes the remaining backlog serially, while each story may perform multiple external requests with 30-75 second timeouts. Because commits happen only after that scan returns, a run can remain opaque for an hour with no branch progress even when the strict repair engine itself is behaving correctly.

The catalogue is currently at 17/123 runtime PASS. The visual standard must not be weakened: every PASS story still requires four distinct relevant usable local photos plus one relevant local logo, with `story_runtime.coverage()` as the only completion authority.

## Goals

1. Every workflow invocation is bounded in wall-clock time and number of stories attempted.
2. One difficult class, especially logo-only identity work, cannot starve photo-repair work elsewhere in the backlog.
3. Every validated catalogue improvement is checkpointed to the repair branch promptly instead of being held until a long scan ends.
4. Operators can see which story is being attempted, how long it took, and why it stopped.
5. A safe bounded stop is distinguishable from an invariant/system failure.
6. The relevance, dedupe, logo-identity, and runtime PASS gates remain unchanged.

## Non-goals

- Do not relax `DIRECT` / `STRONG_CONTEXT` requirements.
- Do not count remote, duplicate, weak/generic, wrong-entity, missing, or unreviewed assets.
- Do not guess logos for stories without a provable exact identity.
- Do not merge PR #2 or enable Story publishing.
- Do not add parallel branch writers; repair writes remain serialized.

## Architecture

### 1. Bounded story queue

Replace the catalogue-wide fallback scan with a bounded per-run queue. The workflow will attempt at most 12 unresolved stories in one invocation by default. The queue is built from fresh `story_runtime.coverage()` results at run start.

Queue ordering is class-aware:

1. stories that still need photos, including mixed photo+logo stories;
2. logo-only stories.

Within each class, keep deterministic smallest-gap ordering. This prevents a block of unresolved logo-only identities from starving stories whose photo deficits can still be repaired safely.

A run is not required to exhaust the entire unresolved catalogue before stopping. Resumability comes from authoritative runtime coverage: completed work disappears from the unresolved queue on the next invocation.

### 2. Hard per-story budget

Each story attempt runs in its own subprocess with a hard 150-second wall-clock budget. A timed-out story is recorded as `TIME_BUDGET_EXCEEDED` and skipped for the rest of that invocation. The run continues to the next bounded story unless an invariant violation occurs.

External source adapters retain their existing fail-closed behavior and individual request timeouts. The hard story budget is an orchestration guard, not a relevance shortcut.

### 3. Overall workflow budget

The GitHub Actions repair job gets `timeout-minutes: 30`.

The workflow also stops beginning new stories after approximately 25 minutes of elapsed repair time, leaving several minutes for validation, runtime-board generation, checkpoint push, and artifact upload.

### 4. Immediate validated checkpoints

After any story attempt produces a runtime-visible deficit reduction:

1. rerun the bulk/runtime regression suite;
2. rebuild the authoritative runtime review;
3. commit only `images/**` and `stories.txt` changes;
4. rebase and push immediately to `repair/story-visual-coverage`;
5. continue from the refreshed branch state if time remains.

No write is committed merely because a registrar claimed success. `story_runtime.coverage()` must show the expected deficit reduction first.

### 5. Observable lifecycle logs

Every story probe prints a compact lifecycle record:

- `START story=<title> class=<photo|mixed|logo-only> deficit=<n>`
- `END story=<title> elapsed=<seconds> rc=<code> result=<label>`

The job summary records:

- start and final authoritative PASS counts;
- number of stories attempted;
- number timed out;
- number that made safe progress;
- number that made no progress;
- last attempted story;
- final runtime status distribution.

This makes a long-running job diagnosable without waiting for completion.

### 6. Exit and GitHub status semantics

Internal repair codes remain fail-closed:

- `0`: catalogue is exactly 123/123 PASS;
- `10`: safe progress was made but backlog remains;
- `2`: bounded slice finished with no safe progress;
- `3`: invariant violation.

At the workflow level, codes `0`, `10`, and `2` are normal bounded outcomes and should finish the job successfully while clearly reporting `COMPLETE`, `PARTIAL_PROGRESS`, or `NO_PROGRESS` in the summary. Only invariant violations, test failures, unexpected system errors, or push failures mark the GitHub workflow as Failure.

This avoids presenting an expected bounded stop as a broken workflow while preserving the distinction between completion and partial work.

## Files expected to change

- `.github/workflows/bulk-visual-repair.yml`
- `tools/bulk_visual_board.py` or a small queue helper if needed for class-aware ordering
- `tools/bulk_visual_repair.py` only where needed for single-story execution/result reporting
- `tests/test_bulk_visual_workflow.py`
- `tests/test_bulk_visual_board.py` and/or `tests/test_bulk_visual_repair.py`

No runtime relevance implementation or approval ledger semantics should change.

## Testing

Implementation follows RED -> GREEN.

Required regressions:

1. queue puts photo-needed/mixed stories ahead of logo-only stories;
2. workflow attempts no more than the configured per-run story limit;
3. each story command is wrapped in a hard timeout;
4. overall repair job has a 30-minute timeout;
5. progress causes validation and an immediate push before the next story;
6. zero-progress bounded slices do not scan the entire catalogue;
7. timeout of one story does not abort later stories;
8. invariant exit code 3 still aborts immediately and fails the workflow;
9. workflow summary distinguishes COMPLETE / PARTIAL_PROGRESS / NO_PROGRESS;
10. existing strict runtime relevance and repair tests remain green.

## Completion criteria

The runner redesign is complete only when the new regressions pass, the existing strict visual tests pass, and a fresh manual run demonstrates all of the following:

- no single story exceeds its hard budget;
- no invocation exceeds the overall workflow budget;
- progress is checkpointed during the run;
- a logo-only block cannot prevent a later photo-needed story from being attempted;
- the authoritative board never regresses;
- the runtime visual standard remains unchanged.
