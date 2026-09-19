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
Focused selection correction deployed via PR #209, merge 6e78f87e077ce8be6330e4a02f702aa4f72ae342.
Fresh shadow run 35460577945 is in progress, mode=shadow/lane=both.
Engine: 8190bec79f39e9f9f5dbd16d7511df7a5532feabf8fa2d9e9933a739a422ab3a. No new package is cleared for posting yet.
- Both lanes use dated reporting and require the matching original article.
- Local timing checks and expiry now match daily behavior; no evergreen seed fallback.
- Independent review explicitly checks current attention and owner feedback.
- Exact rejected triggers are excluded before research; new developments on the
  same subject remain eligible. Curated feedback is versioned in feedback.py.
- Each feed gets bounded candidate space, retaining Saudi-source opportunities.
- Final full v2 suite passed 175 tests; independent reviewer also passed all 12
  attention tests and found no blocking issues. GitHub offline CI passed.
  Bot compile/import checks passed.
Previous shadow run 35459403406 was cancelled without completed/cleared packages.
Its historical state and cost reservations remain intact.
Watchdog and audience analytics remain unimplemented and outside this slice.

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
Finish shadow run 35460577945, inspect completed cards and original-source
attention evidence, and record
exact pass/hold reasons. Do not publish during this validation step.
Then resume watchdog stage 1. A GitHub watchdog cannot independently recover
from a GitHub scheduler outage; assess an external scheduler separately.

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
  is historical; its original $3 ceiling is superseded by the deployed $10/day
  commissioning ceiling authorized in this session.
- Keep existing Saudi Arabic style, broad audience relevance, flexible story
  length, relevant images and independent factual/visual review.
- Audience learning and sustained reliability are not yet established.
- A historical POSTED receipt is evidence of delivery at that time, not proof a
  post remains visible; account for subsequent deletions or replacements.
