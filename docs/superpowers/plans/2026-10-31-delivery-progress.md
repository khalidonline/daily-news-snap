# SDD ledger — plan: docs/superpowers/plans/2026-10-31-ready-package-delivery.md

Base: a8ff64119a52cbfe18195ce072d2538fa69c3a4a.
Method: inline implementation, final fresh reviewer, no live publication.
Pre-flight: Task1 seal feeds Task2 authorization checks; approval fields must
change without invalidating content, all other manifest fields stay sealed.
Ruling: reuse existing publisher CLI entry points instead of duplicating API
logic — preserves all live guards — adds a small Python-process startup cost.
Ruling: preparation is a non-authorizing integrity record, not a fabricated
owner/visual approval — final shared validator remains mandatory — a draft can
be prepared yet require editorial review before authorization.
Ruling: use isolated clean checkout per approved plan, leave dirty original
checkout intact. No master settings changes needed; existing design tokens stay.

Task 1: complete. Fourteen preparation tests observed RED (module missing) then
GREEN (14 passed). No network or approval mutation; bytes/settings/review changes
invalidate readiness. Draft preparation is deliberately not design certification.

Task 2: implementation complete. Eight delivery tests observed RED (missing
module), then GREEN; 22 new tests pass. Extracted pure archive authorization
preflight; fixed workflow defaults to prepared-information with explicit legacy
Story-only mode. No publisher mutation guards or journal identities changed.
Ruling: retain explicit legacy-story mode for compatibility, never automatically
fall back when prepared.json is missing — prevents accidental partial delivery;
older callers must deliberately select their former route.
Baseline full suite before changes: 94 failed, 1127 passed, 21 errors (legacy
fixtures/workflows). These are not evidence of regressions from this change.

Task 2 verification: 81/81 targeted preparation, delivery, bundle, archive,
design-contract and route-inventory tests passed. Final read-only fresh review
found no Critical/Important defect; reviewer independently ran 43 passing tests.
Final: minor (deferred): retry integration test counts unique manifest paths,
not create attempts; existing real publisher tests cover idempotency, but the
new orchestrator test should use a counting provider/journal fake.
Final: minor (deferred): queue latency is not emitted by this CLI; it currently
reports preflight/Story/archive/total only. Queue timestamps remain external.
Final: Ruling: live credentials, provider performance and actual publication are
unverified — no live send is authorized in this task — speed remains unmeasured.
Final: Ruling: editorial/visual/rights evidence remains the existing reviewer's
responsibility — this code checks bindings, not semantics — bad editorial input
still needs human review.
Final: Ruling: archive's existing lack of live-main archive-approval reread is
unchanged; manifest live approval check remains — separate archive revocation
hardening is outside this latency change — archive-only revocation has limits.

Task 3: documentation complete; deployment NOT performed. Full repository suite
still fails: 96 failed, 1147 passed, 21 errors. 94 failures and all21 errors were
present before changes. Two additional failures are repeat-run contamination:
out.png.commons-title left by the baseline run makes a generic photo appear
acceptable; baseline's generated visual cache makes metering test skip its fake
paid request. Neither affected module changed in this branch.
Final: Ruling: finishing-a-development-branch requires stopping on a failing
full suite; preserve tested branch and do not deploy to main — no claim of
activation — user does not yet receive the new production route.
No main updates, no workflow dispatch, no paid generation, no live publication.

## Continuation authorized by owner («كمل»)

Investigated blockers rather than restoring removed legacy workflows. Corrected
test isolation (temporary photo/cache paths and restored sys.modules), froze
only a historical Spotlight fixture's test clock, and normalized missing or
invalid readability manifests into the existing fail-closed ReadabilityError.
The two missing-manifest tests were RED before this guard correction, now GREEN.
Production expiration, approval and publishing checks remain intact.

Prior minor items resolved: retry integration now exercises real publish and
save_story journal logic with counting provider fakes, including an ambiguous
archive create and subsequent recovery. Queue duration is explicitly external
to CLI timing; no approval-to-post speed claim is made.

Verification: actual active CI command, THEME=light FONT_FAMILY=Almarai
python -m pytest tests/test_v2_*.py -q: 642 passed,208 subtests passed,70.51s.
Repair regression set:68 passed,4 subtests. Fresh review of continuation:
no findings; independent reviewer ran95 passing tests and2 subtests.
The publication-contract workflow now adds the preparation/delivery and original
Story/archive tests without removing any existing checks.

Ruling: use the repository's existing active publication CI gate, now expanded,
for this scoped integration, while reporting legacy whole-repository failures
separately. Earlier blanket stop conflated retired workflows with the current
publisher; do not resurrect them, suppress tests or bypass a protected branch.
Cost: unrelated legacy tests remain technical debt, not a claim of a green full
repository. All active v2 tests must pass before main update.
