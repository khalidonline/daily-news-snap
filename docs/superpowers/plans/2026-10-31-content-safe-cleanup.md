# Content-safe Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove a proven retired route from active maintenance without losing content or recovery evidence.

**Architecture:** Hash-protect content first. Archive one independent, retired
Story-to-Telegram workflow and its static test companion; retain shared modules
and everything whose dependencies or completion status remain uncertain.

**Tech Stack:** Git, Python, pytest, JSON manifest, inactive text archive.

**Spec:** docs/superpowers/specs/2026-10-31-content-safe-cleanup.md

## Global Constraints

- No posting, paid generation, schedule changes or remote history deletion.
- Do not touch publication receipts, sources, assets, approved exports or settings.
- No blanket removal by age, filename or test failure.
- Old dirty worktrees remain intact; implement from fresh main in isolation.
- No weakening current design/approval/quota/idempotency gates.

## Review Focus

1. A mixed content/code directory must remain protected byte-for-byte.
2. A shared legacy-named module such as news_bot must not be removed.
3. An archived workflow/test must preserve exact source bytes and restore path.
4. Current template tests must not be deleted to obtain a green result.
5. Receipt branches and Library content must remain unchanged.

### Task 1: Content preservation gate

Files: create tools/verify_content_preservation.py,
tests/test_content_preservation.py, archive/content-preservation-20261031.json.

Interfaces: snapshot(root, tracked_paths) -> dict mapping protected relative
paths to SHA256; verify(root, snapshot) -> raises on missing/changed protected
files. Read-only verification; no automatic repair, publishing or deletion.

- [ ] Write failing tests: changed source, missing approved export, changed
  receipt JSON and mixed-directory .py all fail; unchanged snapshot passes.
- [ ] Implement the read-only guard and generate the index from the pre-cleanup
  tracked tree. Include all roots in the spec and other non-executable content.
- [ ] Run the tests and inspect the protected-file inventory; retain base commit.
- [ ] Commit guard/index only after verification passes.

### Task 2: Retire the isolated Story-to-Telegram route

Exact proposed mapping:

| Existing path | Archive path |
|---|---|
| .github/workflows-disabled/story-approved-to-telegram.yml | archive/retired-story-telegram/story-approved-to-telegram.yml.txt |
| .github/workflows-disabled/story-approval-binding-ci.yml | archive/retired-story-telegram/story-approval-binding-ci.yml.txt |
| tests/test_story_approval_artifact_binding.py | archive/retired-story-telegram/test_story_approval_artifact_binding.py.txt |

Create archive/retired-story-telegram/manifest.json with base commit, SHA256,
original/new paths, retirement reason and inverse restore instructions.
The route is already absent from .github/workflows; tests only inspect that
missing route. Do not archive mixed test files such as
tests/test_topic_workflow_image_policy.py or tests/test_breaking_manual_reproduction.py.

- [ ] Search inbound references across active workflows, scripts and tests.
  Stop that file's move if a live consumer is found; retain historical references.
- [ ] Verify copies byte-for-byte before removing original paths; protect the
  three explicit operational moves as exceptions to the index, not broad roots.
- [ ] Add preservation tests for the exact archive mapping and restore hashes.
- [ ] Refresh reviewed executable inventory; verify content index.
- [ ] Run THEME=light FONT_FAMILY=Almarai python -m pytest tests/test_v2_*.py -q;
  run the full suite and report every remaining failure separately.
- [ ] Fresh read-only review, then approved integration to main with expected-SHA
  lease. No dispatch. Verify deployed hashes and protected content unchanged.

## Follow-up boundary

The other20 disabled workflow files (including README), dated live workflows,
legacy mixed tests and experiments are inventory candidates, not approved
deletion targets in this batch. Audit dependents and publication receipts first.
Current template test expectations need updating to the master, not archival.

## Self-review

This batch is deliberately recoverable and small; it does not pretend that
three moves clean the whole repository. Content and shared-code preservation
have explicit gates. No remote content write is part of implementation.
