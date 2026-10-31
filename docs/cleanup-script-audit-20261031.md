# Batch 11: root-script dependency inventory

Base:809711a6f865ee4bd585f062205288793883393f.
Scope: all49tracked root-level Python files, with original paths and SHA256 in
cleanup-root-script-inventory-20261031.json. This is an inventory, not a move
manifest. No script has been moved or deleted.

The conservative text scan finds candidate incoming references for32files;
17have no incoming reference in the selected runtime/workflow set. Textual
matches include workflow path filters and comments, so they do not establish
runtime reachability. Absence does not establish retirement. A second scan of
tracked docs, tests, disabled workflows and configuration found references for
all17. Each file remains intact under the user's ambiguity-preservation rule.
For four dated scripts the incoming reference is only route-inventory.json;
that is an inventory record, not evidence of use. Their table decisions rely
on source inspection of saved-artifact provenance and unresolved recovery.

Scan rule: literal filename, 'import <stem>' or 'from <stem> import', excluding
self; candidate consumers are tracked .py files and active-workflow files,
excluding archive/, tests/, approved/, drafts/, review/, docs/ and disabled
workflows. This intentionally does not parse ASTs or prove dynamic reachability.

## Resolution evidence for the17 no-runtime-reference candidates

| Files | Evidence / decision |
|---|---|
| ask_card.py, preflight_stories.py | CLAUDE.md documents manual use; retain |
| batch_review.py | Disabled workflow consumer; safe_publish_cards dependency; manual/retirement status unresolved, retain |
| breaking_watch_entry.py | Five current test modules consume it; retain runtime coverage |
| daily_news_fresh_runner.py | Disabled daily route and six current test modules; retain |
| daily_slot_scheduler.py | Current scheduler tests; retain |
| scheduled_story_selection.py, season_aliases.py | Disabled entrypoints and current behavior tests; retain |
| shared_schedule_gate.py, story_delivery_recovery.py | Current tests and protected verification records; retain |
| topic_delivery_guard.py | Current delivery guard tests; retain |
| recover_held_local.py | Shared-budget tests reference it; retirement not established |
| review_package.py | Manual sealed-journal review utility documented in docs/reviews/2026-09-26-owner-review-phase.md; retain |
| finish_caption_20260926.py, repair_saved_trial_20260926.py | Both refer to saved slot autopilot-2026-09-26-daily-shadow-5771c0d01ff16a95; recovery completion not established, retain |
| validate_saved_local_20260926.py | Reuses source_validation_slot autopilot-2026-09-25-local-live and sealed image hashes; retain |
| seal_starbucks.py | Reconstructs approval/review artifacts for approved/starbucks-20261030; preserve provenance, do not execute |

news_bot remains imported by publishing_v2/preview.py and
publishing_v2/preview_package.py, along with other callers. All three benchmark
scripts have active workflow references. No blanket removal is justified.
Protected-root scripts in approved/drafts/review are outside this root-only
inventory and remain protected. The receipt branch was neither fetched nor
modified. Remaining dated-route/recovery uncertainty is explicit, not proof
of an unused file.

## Native review-budget audit finding

resume-budget-blocked-local-review.yml runs resume_budget_blocked_review.py.
Its review_once prepares payload, reserves on the shared Ledger before the
provider request, then settles actual cost. main constructs that Ledger with
autopilot_daily_limit. This explains why requiring an injected guard's display
name is not enough to establish the actual safety property. Behavioral parity
is still pending; the failing workflow-budget test is retained unchanged.

## Verification

Documentation/inventory only; no runtime, test, workflow, content or master edits.
Fresh isolated full baseline:6failed1219passed237subtests,82.64s,one existing
Pillow deprecation warning. Same six failure identities as batch10; no new
failures. No executable/test changes, so this is also the post-inventory code
baseline. All49inventory paths and SHA256 verified against tracked source;
1775protected files unchanged. Existing out/ left untracked/untouched.

Retained failures:
```
approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_all_five_current_approvals
approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_final_nvidia_order_and_media
tests/test_daily_budget.py::WorkflowBudgetTests::test_paid_workflows_cannot_override_guard_python_path
tests/test_external_autopilot_trigger.py::ExternalAutopilotTriggerTests::test_autopilot_uses_external_push_trigger_not_github_schedule
tests/test_external_autopilot_trigger.py::ExternalAutopilotTriggerTests::test_reviewer_recovery_is_bounded_and_cannot_publish
tests/test_model_role_experiment.py::ModelRoleExperimentTests::test_selected_frozen_cases_fit_under_hard_reservation_cap
```
No paid calls, schedules, live publication, receipt access or external content
mutation. Only offline publication-contract workflow matches these doc paths.

## Follow-up: native recovery is fail-closed, not equivalent

On base0495d5df438b21534395df0c67094ee77860ea77, invoked
resume_budget_blocked_review.review_once({}, [], [], Ledger(MemoryStore(),
limit_micro_usd=3000000)) with providers._request replaced by a forbidden
transport. Actual result: BudgetBlocked, "free selection and a stable package
identity are required"; provider attempts0. MemoryStore is the existing test
utility; no credentials/network/real ledger used.

daily_budget.Ledger.reserve requires context package_id and stage for
autopilot:reviewer. resume_budget_blocked_review.main builds the Ledger without
that context and review_once does not add it. Hence the route cannot currently
reach a reviewer request even with an empty daily ledger. This is not evidence
of successful budget integration. recover_held_reviewer also constructs its
Ledger without context by inspection; that second route was not executed here.

Decision: keep the failing workflow guard test; no blanket native-ledger
exemption. Do not restore paid legacy execution, synthesize approval/context,
raise caps or weaken package authorization as part of cleanup. A separate
recovery decision must establish the saved package identity and current scope
before any functional repair. Other cleanup work is not blocked by this.
