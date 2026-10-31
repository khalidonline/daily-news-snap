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
