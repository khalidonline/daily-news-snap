# Retired workflow-policy tests verification

Base:1566839a9ca5ef5a3674bb3796487e29db2839c5.
Archived full originals and verified SHA/base bytes. Existing2Breaking removal
guards unchanged. Replaced only obsolete YAML expectations;8targeted pass.
Current v2/preservation:654pass,208subtests,73.13s.
Full isolated export:7failed,1215passed,0errors,237subtests,1warning,87.44s.
Baseline32failed1213passed. Failure/subfailure comparison has no new IDs and
only removed the archived policy assertions. Previous Pillow warning retained.
1775protected files unchanged. Reviewer verified originals,guard identity,
runtime/budget coverage unchanged and independently reran8pass. No findings.
Reviewer excluded evolving evidence docs/untracked out/ and pending suites;
root verified final logs. out/ remains untouched and uncommitted.
No production/workflow/limits/content/receipt changes. Only existing offline
publication-contract matches push paths; no live or paid dispatch.

## Remaining diagnostic work (not retirement assumptions)

- Two historical saved-story approval fixture failures: preserve approved data.
- Breaking seen-memory daily cap: inspect frozen test inputs and runtime behavior.
- Workflow budget policy: inspect actual active credential-bearing routes.
- Two active autopilot/recovery expectation failures: do not archive active checks.
- Model experiment reservation cap: do not raise limits to obtain green tests.
- Finish script dependency audit; retained shared modules are not dead by age.

```text
No new failures; only archived workflow-policy test failures/subfailures removed.
FAILED approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_all_five_current_approvals
FAILED approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_final_nvidia_order_and_media
FAILED tests/test_breaking_watch_seen_memory.py::BreakingWatchPersistentHeadlineMemoryTests::test_successful_review_marks_daily_cap
FAILED tests/test_daily_budget.py::WorkflowBudgetTests::test_paid_workflows_cannot_override_guard_python_path
FAILED tests/test_external_autopilot_trigger.py::ExternalAutopilotTriggerTests::test_autopilot_uses_external_push_trigger_not_github_schedule
FAILED tests/test_external_autopilot_trigger.py::ExternalAutopilotTriggerTests::test_reviewer_recovery_is_bounded_and_cannot_publish
FAILED tests/test_model_role_experiment.py::ModelRoleExperimentTests::test_selected_frozen_cases_fit_under_hard_reservation_cap
Protected files unchanged: 1775
```
