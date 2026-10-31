# Cleanup batch 9: deterministic review-cap test

Base: 7306bc65ab3b72522d30a1d6a1ea981ee40cc52a.

## Scope and root cause

`test_successful_review_marks_daily_cap` expects `test-stamp`, but its module
uses `sys.modules.setdefault` to provide a fake news_bot. When real news_bot
has already been imported, breaking_watch binds the real ksa_stamp function.
Patching ksa_now does not patch that separately imported function. The full
suite therefore records the wall-clock stamp rather than the fixture stamp.

Reproduced with real news_bot imported before pytest: 1 failed, 8 passed.
The repair patches ksa_stamp where breaking_watch consumes it, within this
test's existing context manager. Both normal collection and real-news_bot-first
collection then pass all 9 tests. Assertions on reviewed state, stamp and
released lock are unchanged. No production code or daily cap is changed.
The test still detects a missing stamp append, missing reviewed flag or failure
to clear the lock; it does not claim to test news_bot's timestamp formatting.

## Remaining failure diagnosis (not repaired in this batch)

- Two October 7 saved-story tests invoke prepare with historical approvals and
  the current clock; approval validation rejects the expired window. Protected
  approved content and approval lifetime remain untouched.
- The workflow-budget test expects a named injected guard in the existing
  resume-budget-blocked-local-review workflow. Its Python runner imports the
  shared Ledger and reserves before request; a full equivalence audit is still
  needed before changing the test. Do not archive this active route.
- External-autopilot tests expect direct input-mode environment expressions;
  the current workflow uses a route-resolution step instead. The other check
  expects reviewer max_tokens 4096 while the current script specifies 4800.
  These require behavioral coverage, not blind replacement of string literals.
- Model-role experiment assumes all selected calls fit a $0.75 reservation;
  their calculated maximum is $0.896918. The runner has a cost_cap_reached branch
  before calling a candidate. Keep the cap; verify skip behavior in follow-up.

## Verification

Full isolated before: 7 failed, 1215 passed, 237 subtests, 1 existing Pillow
deprecation warning, 86.06s. After: 6 failed, 1216 passed, 237 subtests, same
warning, 83.83s. No new failure IDs; only the review-cap fixture failure removed.
Current-path suite: 654 passed, 208 subtests, 68.58s:
`THEME=light FONT_FAMILY=Almarai python -m pytest tests/test_v2_*.py tests/test_content_preservation.py tests/test_retired_story_archive.py -q`.
No old schedules, paid requests or live publication are executed.
All 1775 protected files verified unchanged after the test-only edit.
Untracked out/ remains untouched and excluded.

Retained failures (not hidden or counted as successes):

```
approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_all_five_current_approvals
approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_final_nvidia_order_and_media
tests/test_daily_budget.py::WorkflowBudgetTests::test_paid_workflows_cannot_override_guard_python_path
tests/test_external_autopilot_trigger.py::ExternalAutopilotTriggerTests::test_autopilot_uses_external_push_trigger_not_github_schedule
tests/test_external_autopilot_trigger.py::ExternalAutopilotTriggerTests::test_reviewer_recovery_is_bounded_and_cannot_publish
tests/test_model_role_experiment.py::ModelRoleExperimentTests::test_selected_frozen_cases_fit_under_hard_reservation_cap
```

Fresh read-only reviewer independently reran both targeted collection orders
(9 passed each) and found no Critical, Important or Minor issues in this patch.
Reviewer set aside pending full/current tests, protected-hash verification,
broader route/cap diagnostics, untracked out/, timestamp-format behavior and
whole-cleanup completion. Root rulings: full checks and protected verification
are evidenced separately here; broader work is explicitly incomplete; out/
is preserved; timestamp formatting is outside this fixture's contract. No
production safety or complete cleanup claim follows from this bounded repair.

Push inspection: current mapping-style push triggers do not match these test
and documentation paths. Only publication-contract.yml's list-style push runs;
it is offline, read-only and runs contract tests. No live posting/generation
trigger file or workflow is changed. Integration uses current-main SHA lease.
Ruling: owner explicitly authorized safe tested batch integration while reporting
the pre-existing red baseline; this is not a declaration that the development
branch or broad cleanup is complete. Retain worktree/checkpoint for the six
remaining failures and inventory work. No workspace deletion.
