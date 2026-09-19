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
Recovery and commissioning headroom deployed:
- PR #210 merged as fa8d05e45cd17520a89628e24b317db412034ca5: separately budgeted
  malformed-JSON retry, validated redirects, visual availability before drafting.
- PR #211 merged as 3849dde3a0c589d877ca706fbf499f4bf929939c: explicit $20/day
  commissioning ceiling; legacy default $3 and lower caller caps preserved.
- 184 publishing tests pass; independent review and CI pass for both changes.
  22 budget and 5 store tests also independently pass. The pre-existing legacy
  WorkflowBudgetTests assertion does not recognize native v2 budget integration.
- Trial 35465530726 finished held: daily reached rendering then BudgetBlocked;
  local exhausted three candidates with insufficient eligible images. Cost $0.173828.
- Final-engine trial 35465831225 is RUNNING, shadow/both, no publishing.
  Engine 3643ea84b8f86e478ebf9618a3fe8fd2c6dfd4bc8bd72a04c0e619495bc11f34.
  Reviewer reservation succeeded under $20. Daily M&S draft received factual and
  visual repair feedback: 100 years making clothing is not company founding;
  repeated storefront imagery needs more variety. Allow bounded repairs to finish.
- All historical charges and unresolved reservations remain intact.
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
Inspect completion of shadow trial 35465831225 and its daily/local journals under
snapchat-api-state. Do not cancel or repeat a working run. Resolve concrete remaining
failures if needed, then inspect successful rendered cards and current-source evidence.
Record actual outcomes and cost; preserve prior held slots and reservations.
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
