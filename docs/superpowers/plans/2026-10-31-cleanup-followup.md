# Cleanup follow-up: mixed Topic test batch

Authorization: owner requested scheduled autonomous continuation, small verified
batches and main integration, preserving all content and current safeguards.
Base: 0f69fbb2f6d60072c3e11cd29fca00b249c00675.
Spec: ../specs/2026-10-31-content-safe-cleanup.md.

## This batch

1. Re-run full baseline in an isolated export; do not write real state.
2. Preserve the full original tests/test_topic_workflow_image_policy.py in
   archive/retired-topic-workflow/test_topic_workflow_image_policy.py.txt,
   with SHA256, base commit and restore instructions.
3. Replace only its obsolete active-topic-workflow assertion with a regression
   guard that the retired Topic workflow remains absent from the active folder.
   Keep all seven image relevance/provenance/generation safety methods unchanged.
4. Verify original archive bytes, unchanged seven ASTs, dated content index,
   targeted tests, current v2 tests and full-suite failure IDs. Fresh review and
   expected-SHA integration; no executable or workflow changes.

## Inventory decisions / next bounded batches

- 19 YAML definitions plus README remain in workflows-disabled. This directory
  is already inactive; moving all of it adds no runtime benefit. Retain for now.
- Mixed Breaking file: 7 runtime tests + 2 obsolete workflow tests. Shared slot
  file: 11 runtime tests + 2 obsolete workflow tests. Split in next batch after
  exact archive, preserving runtime methods; do not remove entire test files.
- Daily review setUpClass loads missing daily.yml before all 16 tests; 5 test
  methods concern runner behavior/source rather than workflow. Separate setup
  before judging their outcomes. Never report those tests passing while blocked.
- news_bot is imported by both publishing_v2/preview.py:34 and preview_package.py:66.
  Keep it and its dependencies.
- model_role_experiment and model_quality_benchmark have active workflow
  consumers (model-benchmark-offline, model-quality-benchmark, model-role-experiment).
  Keep them; a reservation-cap failure does not justify raising the cap.
- Dated delivery routes remain until receipt/recovery dependencies are resolved.
- Update the four current fixed-template expectations in a later batch against
  the current master, not by altering the approved design or suppressing tests.

## Push safety

All mapping-style push triggers were inspected on this base: they are path-scoped
and do not match this batch's tests, docs or text archive. The list-style
publication-contract workflow runs offline on push and retains read-only access.
Recheck latest main and triggers immediately before integration.

## Checkpoint after batch 10

Completed batch details are in cleanup-progress.md; do not rerun their edits.
The model experiment's full-comparison reservation check is intentionally kept:
it blocks an incomplete manual paid comparison. Separate offline tests now
cover cost-cap skip/exact-boundary behavior without increasing any limit.
Keep active experiments and shared news_bot based on recorded consumers.

Remaining sequence:
1. Audit native-ledger recovery routes against the generic injected-guard test;
   prove behavioral equivalence before revising expectations. No blind exceptions.
2. Replace obsolete active-route string expectations only with stronger offline
   behavior coverage, preserving shadow/live authorization and bounded review.
3. Keep protected historical approval fixtures untouched unless a separate
   test-only clock strategy preserves both historical validity and expiry tests.
4. Finish script/dated-route dependency inventory; uncertain live/recovery
   consumers stay in place. No archival solely because a script is old.
5. Full isolated verification and content index comparison; report retained
   pre-existing blockers explicitly. Do not claim green by suppressing tests.
