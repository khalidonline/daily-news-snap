# Remaining workflow budget failure — 1 November 2026

Base main: 91027f56bde21a0f2097cb838af8390baa839a96.
Owner requested repair of the remaining shared-budget workflow failure.

## Root cause and bounded resolution

The old test required the text of an injected budget-installation step. Several
legacy workflows instead use native ledgers, and some historical previews use
direct provider transport. The old urllib.urlopen interception alone is NOT
proof of coverage: publishing_v2.providers builds a separate opener. Installing
that hook everywhere would neither establish coverage nor avoid double counting
native reservations. No exemption based only on a route name is appropriate.

Resolution is fail-closed containment, NOT paid-route rehabilitation. Ten legacy
workflow jobs now stop with exit 78 at their first unconditional Bash step,
before checkout, dependencies, model credentials or route code. Later paid steps
have default success conditions and therefore cannot execute after the hold.
Files, source datasets, scripts and historical content are retained. Direct
manual execution of those scripts is not changed or authorized by this repair.

Held entry points:

- resume-budget-blocked-local-review.yml
- recover-held-reviewer.yml
- replace-local-package.yml
- publishing-v2-candidate-probe.yml
- publishing-v2-saved-replay.yml
- publishing-v2-first-preview.yml
- publishing-v2-complete-preview.yml
- publishing-v2-evaluation.yml
- model-role-experiment.yml
- reviewer-visual-experiment.yml

This includes the historical manual model experiments: their local/shared
reservations remain in code, but a future paid workflow run needs separate
route-level audit and deliberate removal of the hold. Do not claim these routes
are operational or automatically restart them after tests pass.

Current prepared-card publishing, Story/archive delivery, challenge workflows,
templates and scheduled tasks are unchanged. The existing audited native-agent
autopilot remains subject to its reviewed entry-point and Ledger tests. The
credential-presence-only cloud audit is unchanged: tests bind its reviewed shell
program and run it with dummy values to prove status-only output, not secrets.

## Verification

New gate audit observed RED for all ten previously unheld jobs. Tests exercise
the exit code and reject conditional, ignored, late, or always-bypassed holds.
The audit covers OpenAI and Getty keys as well as Anthropic; unknown routes do
not receive a native-budget exemption. No budget thresholds or runtime Ledger
guards changed. Focused daily-budget suite: 31 passed, 28 subtests passed.
Executable inventory: 233 reviewed entries verified.

Full isolated suite (`THEME=light FONT_FAMILY=Almarai python -m pytest -q`):
**1232 passed, 256 subtests passed, zero failures**, in 86.14 seconds.
One pre-existing Pillow getdata deprecation warning remains; it is not a failed
test. The former workflow-budget failure is now covered by the containment audit,
not removed or skipped. All other project tests still execute.

Read-only push-path analysis matches ONLY publishing-v2-tests.yml (offline).
No trigger file, workflow schedule, manual dispatch, publication, paid model
request, receipt branch or external content storage is touched. Integration uses
expected-SHA, non-forced main update. The containing commit records completion.
