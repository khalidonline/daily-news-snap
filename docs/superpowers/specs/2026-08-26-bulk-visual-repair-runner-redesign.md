# Bulk visual repair runner redesign

Date: 2026-08-26
Status: approved direction, implementation pending

## Problem

The current bulk visual repair workflow can spend an unbounded amount of wall-clock time scanning unresolved stories after a zero-progress batch. The fallback loop probes the remaining backlog serially, while each story may perform multiple external requests with 30-75 second timeouts. Because commits happen only after that scan returns, a run can remain opaque for an hour with no branch progress even when the strict repair engine itself is behaving correctly.

The catalogue is currently at 17/123 runtime PASS. The visual standard must not be weakened: every PASS story still requires four distinct relevant usable local photos plus one relevant local logo, with `story_runtime.coverage()` as the only completion authority.

## Goals

1. Every workflow invocation is bounded in wall-clock time and number of stories attempted.
2. One difficult class, especially logo-only identity work, cannot starve photo-repair work elsewhere in the backlog.
3. Repeated invocations must advance through unresolved work instead of retrying the same hard prefix forever.
4. Every validated catalogue improvement is checkpointed to the repair branch promptly instead of being held until a long scan ends.
5. Operators can see which story is being attempted, how long it took, and why it stopped.
6. A safe bounded stop is distinguishable from an invariant/system failure.
7. The relevance, dedupe, logo-identity, and runtime PASS gates remain unchanged.

## Non-goals

- Do not relax `DIRECT` / `STRONG_CONTEXT` requirements.
- Do not count remote, duplicate, weak/generic, wrong-entity, missing, or unreviewed assets.
- Do not guess logos for stories without a provable exact identity.
- Do not merge PR #2 or enable Story publishing.
- Do not add parallel branch writers; repair writes remain serialized.

## Architecture

### 1. Bounded, class-aware story queue

Replace the catalogue-wide fallback scan with a bounded per-run queue. The workflow will attempt at most 12 unresolved stories in one invocation by default. The queue is built from fresh `story_runtime.coverage()` results at run start.

Queue ordering is class-aware:

1. stories that still need photos, including mixed photo+logo stories;
2. logo-only stories.

Within each class, keep deterministic smallest-gap ordering. This prevents a block of unresolved logo-only identities from starving stories whose photo deficits can still be repaired safely.

### 2. Persisted queue cursor

A small runner-state file, `state/bulk_visual_repair_cursor.json`, records the last attempted position for the photo-needed class and the logo-only class. Queue construction rotates each class after its stored cursor before selecting the next bounded slice.

Rules:

- a successful PASS story disappears naturally because authoritative coverage no longer lists it;
- a no-progress or timed-out story still advances the cursor so the next invocation does not retry the same hard prefix;
- cursor state is deterministic and contains no approval decisions, only orchestration position;
- cursor updates are pushed at the end of a safe bounded run even if no visual asset was added;
- invariant failures do not advance/push the cursor past the offending story.

This makes repeated manual runs resumable without weakening or bypassing any visual gate.

### 3. Hard per-story budget

Each story attempt runs in its own subprocess with a hard 150-second wall-clock budget. A timed-out story is recorded as `TIME_BUDGET_EXCEEDED` and skipped for the rest of that invocation. The run continues to the next bounded story unless an invariant violation occurs.

External source adapters retain their existing fail-closed behavior and individual request timeouts. The hard story budget is an orchestration guard, not a relevance shortcut.

Because a subprocess can be terminated after completing one atomic asset registration but before returning normally, the parent workflow must always compare pre-attempt and post-attempt runtime coverage before deciding what to keep.

For timeout or other non-invariant exits:

- if runtime coverage shows a valid deficit reduction, run the normal validation/checkpoint path and keep the safe progress;
- if runtime coverage shows no valid reduction, restore `images/**` and `stories.txt` to the last committed checkpoint before attempting the next story;
- temporary files under `out/` are never committed.

### 4. Overall workflow budget

The GitHub Actions repair job gets `timeout-minutes: 30`.

The workflow also stops beginning new stories after approximately 25 minutes of elapsed repair time, leaving several minutes for validation, runtime-board generation, cursor checkpoint, branch push, and artifact upload.

### 5. Immediate validated checkpoints

After any story attempt produces a runtime-visible deficit reduction:

1. rerun the bulk/runtime regression suite;
2. rebuild the authoritative runtime review;
3. update the orchestration cursor to the attempted story;
4. commit only `images/**`, `stories.txt`, and `state/bulk_visual_repair_cursor.json`;
5. rebase and push immediately to `repair/story-visual-coverage`;
6. continue from the refreshed committed branch state if time remains.

No write is committed merely because a registrar claimed success. `story_runtime.coverage()` must show the expected deficit reduction first.

If the bounded slice ends safely with no visual progress, validate that the working tree contains no unverified visual changes, then commit/push only the cursor state so the next invocation moves to later unresolved stories.

### 6. Observable lifecycle logs

Every story probe prints a compact lifecycle record:

- `START story=<title> class=<photo|mixed|logo-only> deficit=<n>`
- `END story=<title> elapsed=<seconds> rc=<code> result=<label> before=<gap> after=<gap>`

The job summary records:

- start and final authoritative PASS counts;
- number of stories attempted;
- number timed out;
- number that made safe progress;
- number that made no progress;
- last attempted story in each queue class;
- final runtime status distribution.

This makes a long-running job diagnosable without waiting for completion.

### 7. Exit and GitHub status semantics

Internal repair codes remain fail-closed:

- `0`: catalogue is exactly 123/123 PASS;
- `10`: safe progress was made but backlog remains;
- `2`: bounded slice finished with no safe visual progress;
- `3`: invariant violation.

At the workflow level, codes `0`, `10`, and `2` are normal bounded outcomes and should finish the job successfully while clearly reporting `COMPLETE`, `PARTIAL_PROGRESS`, or `NO_PROGRESS` in the summary. Only invariant violations, test failures, unexpected system errors, rollback failures, or push failures mark the GitHub workflow as Failure.

This avoids presenting an expected bounded stop as a broken workflow while preserving the distinction between completion and partial work.

## Files expected to change

- `.github/workflows/bulk-visual-repair.yml`
- `tools/bulk_visual_board.py` or a focused queue helper for class-aware ordering/cursor rotation
- `tools/bulk_visual_repair.py` only where needed for single-story execution/result reporting
- `state/bulk_visual_repair_cursor.json`
- `tests/test_bulk_visual_workflow.py`
- `tests/test_bulk_visual_board.py` and/or `tests/test_bulk_visual_repair.py`

No runtime relevance implementation or approval ledger semantics should change.

## Testing

Implementation follows RED -> GREEN.

Required regressions:

1. queue puts photo-needed/mixed stories ahead of logo-only stories;
2. queue rotation after the persisted cursor prevents repeated runs from retrying the same hard prefix;
3. workflow attempts no more than the configured per-run story limit;
4. each story command is wrapped in a hard timeout;
5. overall repair job has a 30-minute timeout;
6. progress causes validation and an immediate push before the next story;
7. zero-progress bounded slices do not scan the entire catalogue;
8. timeout of one story does not abort later stories;
9. safe progress completed before a timeout is validated and may be checkpointed;
10. an unproductive/unsafe timeout restores visual files to the last committed checkpoint;
11. invariant exit code 3 still aborts immediately and fails the workflow without advancing the cursor past the offending story;
12. workflow summary distinguishes COMPLETE / PARTIAL_PROGRESS / NO_PROGRESS;
13. existing strict runtime relevance and repair tests remain green.

## Completion criteria

The runner redesign is complete only when the new regressions pass, the existing strict visual tests pass, and a fresh manual run demonstrates all of the following:

- no single story exceeds its hard budget;
- no invocation exceeds the overall workflow budget;
- progress is checkpointed during the run;
- a logo-only block cannot prevent a later photo-needed story from being attempted;
- a second invocation starts beyond previously attempted hard stories rather than repeating the same prefix;
- timeout handling cannot leave unvalidated visual changes queued for a later checkpoint;
- the authoritative board never regresses;
- the runtime visual standard remains unchanged.
