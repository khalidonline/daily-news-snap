# Cleanup batch 10: experiment cap audit, not a cap increase

Base: 4ca6707ab3036f0d5e3dcc14c329484b50a9af01.

## Decision

Retain the failing all-cases-fit preflight in test_model_role_experiment.py.
The manual model-role-experiment workflow runs that preflight before its paid
step. Changing it into a passing skip test would also unblock an incomplete
comparison. The original check is not proven obsolete and is not archived.
Current two-case/six-call maximum is $0.896918, exceeding the existing $0.75
experiment cap. Neither cap, cases, prompts nor workflow are changed.

Add separate offline behavioral tests for the runner's existing reservation
gate. Replace only the HTTP boundary with synthetic provider responses and
pass an explicit environment containing fake keys, no inherited credentials.
Run the actual loop, adapters, accounting and artifact-writing into temporary
directories. The response text is deliberately empty JSON; editorial output
validation is not the subject of these cap tests.

## Evidence

- Existing preflight reproduced: 1 failed, 6 passed, 3 subtests.
- Frozen cases: five transport requests, sixth recorded as cost_cap_reached;
  reserved maximum $0.733462, below $0.75.
- Six reservations at $0.125: all six permitted, total exactly $0.75.
- Six reservations at $0.125001: sixth blocked, total $0.625005.
- Three new tests pass on unchanged production implementation.
- In isolated export only, removing the reservation check makes two new tests
  fail ($0.896918 and $0.750006). Changing > to >= makes exact-boundary test
  fail (5 requests instead of 6). Restoring original code returns 3 passes.
- No paid service, actual credentials, GitHub state, publication or production
  file is used/modified by these checks. Full suite runs in isolated export.

## Dependency audit

The model-role-experiment workflow remains an active manual consumer; retain
model_role_experiment.py rather than archiving it based on this failure.
model_quality_benchmark.py also has active workflow consumers. news_bot remains
shared by supported preview paths. Reviewer-recovery scripts have active
workflow consumers and are not retired by their age. This is a bounded audit,
not proof that all other scripts can be removed.

## Verification status

Full isolated suite: 6 failed, 1219 passed, 237 subtests, one existing Pillow
deprecation warning, 83.19s. Baseline: 6 failed, 1216 passed. No new failure
identities; three new passes. Current-path suite654passed,208subtests,68.92s.
Protected1775files unchanged. Untracked out/ preserved and excluded.

Retained failure identities:

```
approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_all_five_current_approvals
approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_final_nvidia_order_and_media
tests/test_daily_budget.py::WorkflowBudgetTests::test_paid_workflows_cannot_override_guard_python_path
tests/test_external_autopilot_trigger.py::ExternalAutopilotTriggerTests::test_autopilot_uses_external_push_trigger_not_github_schedule
tests/test_external_autopilot_trigger.py::ExternalAutopilotTriggerTests::test_reviewer_recovery_is_bounded_and_cannot_publish
tests/test_model_role_experiment.py::ModelRoleExperimentTests::test_selected_frozen_cases_fit_under_hard_reservation_cap
```

Fresh reviewer independently ran all3 new tests successfully; no Critical or
Important findings. Minor documentation caveat: frozen-case test mocks only
transport, while boundary tests also supply controlled maximum_call_cost
estimates. These are boundary tests, not independent pricing verification.
The test helper's production-cost arithmetic remains real. No code change
requested; wording polish deferred. Reviewer declined full/current suites,
failure comparison, preservation, remote state and mutation reproduction;
root verification is recorded separately, never inferred from review.

Owner-authorized bounded integration does not assert full-suite success.
No posting/generation push path matches these test/docs paths. Only the
existing offline read-only publication-contract push workflow matches.
