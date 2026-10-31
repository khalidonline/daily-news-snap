# Batch12: route resolver fixture

Base:bcc4c71f518eb9161500821e83e2110f39590ca5.
The active workflow no longer binds mode directly to inputs; it resolves mode
and lane in its route step. Test expected obsolete direct expressions and failed.
Replace those two assertions with output-binding checks and execute the actual
embedded resolver in a subprocess with explicit credential-free environment,
temporary output file, and no other workflow steps.

Five cases: ordinary push ignores live/local inputs and stays shadow/daily;
empty manual dispatch defaults shadow/daily; manual local shadow is retained;
invalid mode and multi-lane input both fail without writing output.
Existing push path/no schedule/manual-dispatch checks retained. No runtime or
workflow change, no live publication, no paid calls. This is route-selection
coverage, not authorization proof for existing explicit live promotion paths.
The reviewer-recovery token-limit failure is left intact, not silently updated.

Targeted result:1passed,5subtests,1existing reviewer-recovery failure. Full
suite:5failed1220passed242subtests,81.80s,one existing Pillow warning. No new
failure IDs; only obsolete route fixture failure removed. Protected1775files
unchanged. Remaining failures: two October7approval-window tests,
WorkflowBudgetTests.test_paid_workflows_cannot_override_guard_python_path,
ExternalAutopilotTriggerTests.test_reviewer_recovery_is_bounded_and_cannot_publish,
ModelRoleExperimentTests.test_selected_frozen_cases_fit_under_hard_reservation_cap.
Protected content and all six baseline failure
identities are tracked in prior cleanup reports.

Fresh reviewer found no blocker; identified old report-mode wiring coverage
should be retained. Restored its assertion against route.outputs.mode in the
actual report step. Targeted rerun1passed5subtests,1unchanged failure.
No re-review necessary for the single inspected binding assertion. Explicit
live promotion/downstream authorization remain outside this fixture; no claim
they were certified here. Push matches only offline publication-contract.
