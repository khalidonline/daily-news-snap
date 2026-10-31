# Retained failure repair — 31 October 2026

Base: b3e08eca9b20f418918f64f49dcc76fb09159142.
Scope: fix verified failures without live publication, paid generation, changed
design settings, renewed historical approvals or relaxed spending protection.

## Implemented

1. Historical archive tests use an in-memory 8 October clock at BOTH consumers.
   Original approval JSON, manifest, source, receipt and media bytes remain
   untouched. A new test proves that the original approval fails after expiry at
   each independent boundary. Existing media/order/lineage tests now reach their
   intended validation rather than passing because every approval is expired.
2. Replace the obsolete 4096 source-text check by an offline invocation of the
   actual reviewer, proving its existing 4800 payload, reservation before HTTP,
   receipt and exhausted-ledger rejection. Only HTTP is replaced. This does NOT
   claim the legacy recovery main sets valid package context or is operational.
3. Reduce the manual writer experiment to one case per invocation, comparing all
   three models. The $0.75 cap, output ceiling and provider pricing are unchanged.
   Other cases remain intact in evaluation/event_packages.json for a separately
   approved run; no automatic second batch. Tests retain the oversized two-case
   scenario plus exact/over-cap boundaries using an explicit test configuration.

## Remaining blocker — do not exempt old workflows

`tests/test_daily_budget.py::WorkflowBudgetTests::test_paid_workflows_cannot_override_guard_python_path`
remains unchanged and failing. It expects an injected runtime guard in all
credential-bearing workflows except the audited autopilot. Investigation finds
several different mechanisms, not merely a renamed installation step:

- resume-budget-blocked-local-review and recover-held-reviewer use native Ledger;
  their legacy main functions do not populate the required package/stage context.
  Do not revive those routes or call that a working budget path.
- model-role-experiment has shared reservation and a per-invocation cap.
- publishing-v2-cloud-permissions includes a credential-presence-only step.
- publishing-v2-evaluation has an invocation-local spend ledger, while historical
  preview routes call the provider boundary. Equivalence to the shared daily cap
  cannot be established from the old step-name assertion.

No broad exemption or passing rewrite was added. Completing this item requires
an explicit route-by-route guard integration/retirement decision, not weakening
the test. No legacy workflow was executed, enabled, edited or dispatched here.
Earlier explanation that this was only a stale step label was incomplete.

## Verification

Original targeted reproduction: 5 failed, 44 passed, 22 subtests passed.
New one-case behavior was observed failing before changing MAX_CASES.
Focused corrected archive/recovery/experiment tests: 25 passed, 8 subtests passed.
Full isolated suite (`THEME=light FONT_FAMILY=Almarai python -m pytest -q`):
**1 failed, 1229 passed, 242 subtests passed, 1 Pillow deprecation warning**, in
81.16 seconds. The only failure is the WorkflowBudgetTests method named above.
The initial redirected full attempt ended without a summary and is not counted
as verification; the complete rerun supplies these results. No new failing IDs.

Only the reviewed model_role_experiment.py and historical test executable hashes
are refreshed in route-inventory. No other executable or workflow is changed.
Changed paths can trigger offline v2 checks, not live publishing or generation.
Integration must use current main as parent and expected-SHA non-forced update.
