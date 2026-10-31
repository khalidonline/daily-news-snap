# Pre-review readiness — 2026-10-31

Owner request: complete draft archive/publication metadata and actual placement-overlay review before showing a design. Draft text against the approved template from the start.

## Change

- `publishing_v2.prepared_information prepare-preview` runs existing design-contract validation for each destination before sealing a package. Archive fields and exact media/source review hashes must already be present. Both approvals must remain false.
- `prepare` remains an integrity-only utility; it is not evidence of preview readiness. Delivery authorization and live reconciliation are unchanged.
- AGENTS.md and ready-package-delivery.md now require this pre-review step and text fitting with the approved font, two-line bullet limit and unchanged geometry. Actual overlay review must not be fabricated.
- No template settings, published assets, schedules or publication receipts changed. No live publishing or paid generation was used.

## Verification

Focused readiness, preparation, delivery and route-inventory tests: **27 passed**.

Isolated full suite, with approved renderer environment `THEME=light FONT_FAMILY=Almarai`: **1223 passed, 5 failed, 242 subtests passed**, 82.26 seconds. The five retained baseline failures are:

- approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_all_five_current_approvals
- approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_final_nvidia_order_and_media
- tests/test_daily_budget.py::WorkflowBudgetTests::test_paid_workflows_cannot_override_guard_python_path
- tests/test_external_autopilot_trigger.py::ExternalAutopilotTriggerTests::test_reviewer_recovery_is_bounded_and_cannot_publish
- tests/test_model_role_experiment.py::ModelRoleExperimentTests::test_selected_frozen_cases_fit_under_hard_reservation_cap

An initial unconfigured suite also failed renderer configuration and the intentionally stale executable-inventory hash. The approved environment was restored and the reviewed prepared_information.py hash updated. No protective assertion was removed to pass tests.

Base main: `47f3ebc642856585bd1f6b15c95a17bf446af221`. Changed paths trigger offline v2 tests, not the live publishing workflow. Integration uses an expected-SHA, non-forced main update. The containing commit is the integration evidence.

This change moves preparation ahead of owner review; it does not claim a measured improvement in live publishing time.
