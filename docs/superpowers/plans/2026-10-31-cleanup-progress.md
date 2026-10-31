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

## Follow-up batch 3 — retired Breaking and shared-schedule assertions

Base:a939ac3006542d7c1580c9a2c7e665f9060df112. Owner requested continuation.
Plan:2026-10-31-cleanup-followup.md, mixed-test split step.
Four obsolete assertions reproduced failing;18 runtime methods passed before
changes. Full originals preserved byte-exact in archive/retired-schedule-tests
with SHA256 and restore instructions before editing. All18 method ASTs unchanged.
Replaced four obsolete assertions by three guards against restoring the retired
Breaking, Topic and Story active entrypoints. Targeted21 tests pass.
Ruling: consolidate the two obsolete Breaking workflow-content checks into one
absence guard because the workflow is retired, not a supported entrypoint.
Risk: does not detect a renamed equivalent; no general retirement claim made.
Fresh read-only review found no blocking issues. Minor deferred: guard names
retain historical behavior wording and extra blank lines; no runtime impact.
Reviewer declined full-suite/preservation/remote evidence; root owns those checks
and records results in docs/cleanup-schedule-verification-20261031.md.
No workflow, production, master, receipt or remote content changes authorized.
Next unfinished step: separate DailyReview setup before assessing its runner
tests, then current-template expectations and remaining script dependencies.

## Follow-up batch 4 — unblock Daily runner coverage

Base:a017d3324ccee81c050112bcf8c2f8820695b6ed. Owner requested continuation.
Archived the complete original tests/test_daily_review_workflow.py byte-exact
with SHA256/restore instructions in archive/retired-daily-tests before editing.
Removed only11 obsolete workflow-content assertions (10 daily.yml and1
news-editorial-tests.yml). Removed missing daily.yml read from setUpClass.
Five runner tests are byte/AST unchanged and now execute instead of setup error;
all5 pass, plus one retirement guard (6 targeted pass).
Ruling: retired workflow assertions belong in recoverable archive, not an active
fixture that blocks independent runner tests. No runtime or workflow changes.
Independent reviewer verified archive/hash and unchanged methods and reran6pass.
Reviewer declined full-suite health while pending; root records complete failure
comparison in docs/cleanup-daily-verification-20261031.md before integration.
Next: remaining mixed static workflow assertions, current-template expectations,
and script dependency audit; do not repeat completed Topic/Breaking/Shared/Daily
test separation. Overall cleanup remains incomplete.

## Follow-up batch 5 — current information-template tests

Base:504b6711da07c0d1251fd9b58537bca7e9ca6d0f. Owner requested continuation.
Reproduced4failures/5passes in current template tests. Updated obsolete geometry
expectations to approved_layout_override (title215,closing1575,24px visible ink
gap,equal N+1 paragraph gaps between735/1575); preserved artwork comparisons with
the approved proportional fitting, and sample green within actual header region.
Replaced superseded font comparison acceptance with rejection tests for46Regular,
45Regular,45Bold; existing44Bold/right-aligned continuation test retained.
Gap test starts from valid rendered geometry before injecting a1px line-gap defect,
so rejection is due to the gap, not a missing ink-bounds field.
No renderer, settings, design gate, workflow or content changes.11targeted pass.
Ruling: adapt tests to latest explicit approved master, not production to old
tests. Risk: later owner layout changes require reviewing these explicit values.
Full comparison and final review recorded in docs/cleanup-template-verification-20261031.md.
Broader cleanup remains incomplete: residual retired-workflow assertions and
script/experiment dependency audit. Do not repeat current template test repair.

## Follow-up batch 6 — retired cost-pilot workflow checks

Base:ed9a6bc922076f990d69f94572069283754f8098. Owner requested continuation.
Reproduced3failed+5setup errors in tests/test_daily_cost_leak_policy.py and
tests/test_three_story_cost_pilot_safety.py. Inspected every method: exclusively
static assertions against absent retired workflows; no executable runtime tests.
Archived both originals byte-exact with SHA256/base/restore manifest under
archive/retired-cost-workflow-tests. Replaced with4 guards against active daily,
story,external-clock-receiver,three-story-cost-pilot entrypoints.4targeted pass.
Ruling: retain inactive workflow definitions in workflows-disabled; they are
already archival and protected by dated content index. No cost limits relaxed.
Current ExternalAutopilotTrigger tests reference existing workflows and script;
keep them rather than treating their failures as retirement evidence.
No production,workflow,master,source,receipt or content changes.
Final evidence: docs/cleanup-cost-verification-20261031.md.
Remaining scope includes mixed static workflow tests and current live-route
expectation failures, plus script dependency audit; whole cleanup not complete.

## Follow-up batch 7 — remaining isolated assertions in four mixed tests

Base:5bf03b3a0ab766c382a74c68a76f634547ee1e13. Owner requested continuation.
Reproduced10failed/47passed across StoryDeliveryRecovery,TopicRecoveryHandoff,
BreakingWatch and TopicSnapchat test files. Each removed method only reads an
absent retired workflow file; no runtime behavior was deleted.
Archived all4full originals byte-exact with SHA256 and restore instructions in
archive/retired-mixed-workflow-tests. All47retained method ASTs unchanged;
47targeted pass. Existing retirement guards in other test files remain active.
Ruling: do not duplicate absence guards in every mixed file; use existing
Breaking/Topic/Story guards. Risk: no broad renamed-workflow detection claimed.
No runtime,workflow,content,master or receipt changes. Final verification and
independent review recorded in docs/cleanup-mixed-verification-20261031.md.
Remaining: paid workflow/model usage legacy assertions, existing active route
expectations, historical approval fixtures and script dependency audit.

## Follow-up batch 8 — retired model-usage/paid-workflow expectations

Base:1566839a9ca5ef5a3674bb3796487e29db2839c5. Owner requested continuation.
Inspected complete ModelUsageWorkflowTests and PaidWorkflowPolicyTests. Removed
only expectations of already absent daily/topic/story/breaking/batch-review and
external-clock-receiver definitions. Preserved full originals byte-exact with
SHA/base/restore manifest in archive/retired-policy-tests. Existing two Breaking
retirement methods remain AST-identical; replacement entrypoint guards8pass.
Before25failed6passed including subtest accounting. No runtime model usage,
shared budget tests, cost guards, experimental limits or active workflow changes.
Ruling: obsolete assertions requiring scheduled entrypoints must not resurrect
those entrypoints. Absence guards enforce retirement; old content stays archived.
Untracked out/ was present at start and preserved, excluded from integration.
Final results and independent review: docs/cleanup-policy-verification-20261031.md.
Next: diagnose remaining actual/historical fixture failures (do not archive by
failure alone) and finish script dependency inventory. Cleanup still incomplete.

## Follow-up batch 9 — isolate the review-cap test clock

Base:7306bc65ab3b72522d30a1d6a1ea981ee40cc52a. Owner requested continuation.
Pre-flight: no shared production interfaces changed; only one fixture dependency.
Ruling: patch ksa_stamp at its consumer in the failing test, not news_bot or
breaking_watch production code. The fixture previously depended on import order;
the cost if wrong is masking timestamp formatting, which this daily-cap test
does not claim to cover. Reviewed/stamp/lock assertions remain unchanged.
RED: real-news_bot-first collection1failed8passed; GREEN: same order9passed,
normal isolated collection9passed. No approved content, workflow or cap changes.
Remaining failures are diagnosed, not suppressed; see
docs/cleanup-memory-verification-20261031.md. Full baseline7failed1215passed;
after6failed1216passed, no new failure IDs. Fresh reviewer independently9pass
in both collection orders, no findings. Current-path654passed208subtests;
protected1775unchanged. Bounded integration authorized despite documented
pre-existing failures; not whole-branch completion. Keep checkpoint/worktree.
Next: behavioral coverage for active-route/cost-cap expectations, historical
fixture treatment without modifying approvals, and remaining script inventory.
