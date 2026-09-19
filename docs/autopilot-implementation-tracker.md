# Autopilot implementation tracker

## Working agreement
Implement one small, verifiable stage at a time. Send concise progress updates using:
stage; completed change; verification evidence; remaining work; blocker if any.
Status questions are checkpoints, not cancellation of authorized work. No repeated
approval is needed for already authorized implementation. Never imply development
continues after a chat turn ends.

Update this file at each milestone and before an interruption when possible.
Use precise states: planned, implementing, tested, deployed, verified live, blocked.
Code deployed is not the same as live behavior verified.

## Current checkpoint
Recovery fix deployed through PR #210, merge fa8d05e45cd17520a89628e24b317db412034ca5.
All 184 publishing tests and independent review passed. The workflow trial
35465530726 is running in shadow mode for both lanes; no posting in this trial.
- One separately budgeted JSON-format retry; no retries of refusals, unknown costs
  or semantic rejection. Format errors recorded without raw response text.
- At most three source redirects, each validated by the existing URL allowlist.
- Eligible subject images checked before paid research; catalogue passed to writer.
- Budget headroom correction in progress: September 19 ledger has $4.475385 settled
  and $0.115566 outstanding, leaving less than the reviewer's $5.4096 conservative
  reservation under $10. Explicit commissioning ceiling increased to $20/day under
  existing owner authorization; legacy callers retain their $3 default and existing
  $10 callers retain their own cap. No charges or unknown reservations removed.
- Budget regression tests: 22 pass, including preservation of old entries and cap
  enforcement. A pre-existing workflow test assumes every workflow uses legacy
  PYTHONPATH injection; native v2 instead reserves and settles directly.
No new daily/local pair is cleared for posting. Watchdog/analytics are separate.

## Milestones
| Stage | Scope | Status | Completion evidence required |
| --- | --- | --- | --- |
| 0 | Specialist editorial agents, independent review, bounded repairs, publishing journals, budget and Telegram reporting | Deployed; prior engine verified live | Launch run 35438752317 confirmed two packages / eight frames on September 19; recheck current engine before claiming readiness |
| 1 | Detect missing, stalled, incomplete and successful daily runs | Planned; next | Deterministic tests plus read-only comparison with actual run and receipt state; no paid generation or publishing |
| 2 | Bounded safe recovery | Planned | Tests for missed run, partial delivery, concurrent run, budget exhaustion, expired package and ambiguous provider result; preserve receipt identity, review gates and budget |
| 3 | Schedule watchdog and concise Telegram incident/recovery reports | Planned | Deployed workflow and real monitor execution; deduplicated alerts; obey pause mode; document shared GitHub scheduler outage limitation |
| 4 | Observe daily reliability | Pending operational evidence | Record at least three consecutive Saudi days of both-lane outcomes, delivery receipts, alerts and authoritative daily cost; report failures honestly |
| 5 | Connect available audience metrics | Planned | Confirm provider/account access and metric definitions; real read-only metric retrieval; private storage for audience data |
| 6 | Introduce measured content optimization | Planned | Bounded recommendations from sufficient real data, editorial review preserved, comparison and rollback; never invent engagement evidence |
| 7 | Review platform/model efficiency | Planned | Compare measured output quality, delivery reliability, latency and total cost; vendor-neutral decisions |

## Immediate next action
Finish the $20 commissioning headroom deployment and run the resulting main engine
in shadow mode for both lanes. Inspect resulting cards and current-source evidence.
Record actual outcomes and cost; preserve all prior held slots and reservations.
Do not claim tomorrow's posting is ready until both lanes clear validation.

## Resume procedure
1. Read this tracker, current main and open implementation PRs.
2. Check recent changes from other sessions; retain editorial improvements.
3. Reconcile Actions runs, engine readiness and delivery journals before acting.
4. Continue the first unfinished stage; do not repeat completed paid runs.
5. Update this tracker with commit/PR, tests, actual deployment/run evidence and
   exact next action. If blocked, record the specific access or dependency.

## Evidence and limits
- Historical live launch: https://github.com/khalidonline/daily-news-snap/actions/runs/35438752317
- Existing operations: docs/agentic-autopilot.md (may lag newer workflow edits).
- Existing implementation plan: docs/superpowers/plans/2026-09-17-agentic-autopilot.md
  is historical; its original $3 ceiling is superseded by the explicit $20/day
  commissioning ceiling authorized in this session.
- Keep existing Saudi Arabic style, broad audience relevance, flexible story
  length, relevant images and independent factual/visual review.
- Audience learning and sustained reliability are not yet established.
- A historical POSTED receipt is evidence of delivery at that time, not proof a
  post remains visible; account for subsequent deletions or replacements.
