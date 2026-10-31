# SDD ledger — plan: docs/superpowers/plans/2026-10-31-content-safe-cleanup.md

Base:9171af09a10b9faf2051c50bdeace19aaa360054. Owner approved native execution
and the three explicit archive moves. No content deletion or live dispatch.
Pre-flight: Task1 snapshot must permit Task2's exact operational moves while
protecting content; archived originals are separately SHA-verified.
Ruling: exclude only the three approved moves and operational route-inventory
JSON from the content index. Inventory must change to register the new guard;
it is not publication/content evidence. All other non-code files and all mixed
protected roots remain immutable during this batch. Risk: index is a bounded
cleanup baseline, not a permanent prohibition on later owner-approved edits.
Ruling: isolate execution from dirty prior worktree per approved plan. Existing
test-generated files there remain untouched. No branch cleanup or destructive reset.
Cloud skill scripts are not locally mounted; this tracked ledger records task
boundaries and verification instead. No implementer agents; one final reviewer.

Task1 complete:10 tests observed RED (guard absent) then GREEN. Snapshot covers
1775 tracked protected files at9171af0; read-only verification confirms unchanged.
Remote Library and receipt branches are explicitly outside this local index and
are not accessed or modified. Existing base failures already documented in
docs/ready-package-validation.md; owner authorized bounded cleanup with these
legacy failures retained, not resurrecting retired schedules.

Task2 archive step: copies SHA256-matched before removing the three originals.
12 preservation/archive tests pass.1775 protected files still unchanged.
Reference scan found no active consumer beyond the new archive verifier/tests;
historical documentation references remain for provenance. No shared code removed.
Ruling: full-suite tests run in a disposable exported checkout, since old tests
write source-cache state. This keeps preservation evidence meaningful and avoids
altering real repository state just to run tests. Cost: export is not a Git repo;
any Git-dependent test difference must be disclosed, not hidden.

Task2 complete locally:3 R100 byte-exact renames;1775 protected files match
base and current files. Fresh independent reviewer found no Critical/Important
issues and independently recomputed the complete protected selection/hashes.
Full exported-checkout suite:54 failed,1193 passed,21 errors,237 subtests.
No new failure IDs versus base; exactly6 retired static tests removed from
collection. Remaining legacy failures are preserved by name in cleanup report.
Final: minor (deferred): a future --snapshot from a dirty worktree could imply
HEAD provenance while hashing modified working bytes. This delivered baseline
was independently compared with base blobs; future snapshot hardening remains.
Final: Ruling: no remote Library or receipt-branch mutations are part of this
task; local hashes do not claim a backup of remote stores. Risk: remote state
was not audited, but cleanup does not touch it.
Final: Ruling: restore is documented and archive bytes verified, not executed
against live paths; risk: future restore requires separate approval and review.
Final: Ruling: approved bounded integration uses active publishing tests plus
full-suite baseline comparison; do not resurrect retired schedules to satisfy
their remaining tests. Risk: unrelated legacy technical debt remains visible.

## Follow-up batch 2 — 31 October 2026

Plan: docs/superpowers/plans/2026-10-31-cleanup-followup.md.
Base main:0f69fbb2f6d60072c3e11cd29fca00b249c00675; local HEAD has identical tree.
No earlier cleanup process was running. Existing isolated worktree was clean.
Ruling: keep already disabled workflow files in place for now; archiving them
again gives no runtime benefit. Keep shared modules and active experiment
consumers. Risk: more old files remain until individually assessed.
Ruling: replace only one obsolete Topic workflow test with an absent-entry guard,
preserving the complete original as inactive text and all seven image safety
methods unchanged. No production code changes; existing failing test reproduced
(1 failed/7 passed), new retirement guard tested against simulated presence.
Archive original bytes match base SHA256. Targeted tests:20 passed.
Current v2/preservation suite:654 passed,208 subtests. Full baseline reproduced:
54 failed,1193 passed,21 errors,237 subtests; after:53 failed,1194 passed,
21 errors,237 subtests. Only the replaced obsolete test disappears from failures;
no new failures. Details: docs/cleanup-topic-verification-20261031.md.
1775 protected files unchanged. No current design, workflow, publisher, remote
content or receipt-branch change. Test-generated hero files were moved out of
the worktree into scratch, not deleted or committed.
Fresh read-only review approved the four-file implementation without blocking
findings. Reviewer declined pending suite parity; root verified it afterward.
Reviewer did not judge unrelated failures; all remain explicitly reported.
Next: split the two Breaking and two SharedSchedule static tests, preserving
runtime methods and originals; then separate DailyReview setup. Do not repeat
this Topic batch. Broader cleanup remains incomplete.
