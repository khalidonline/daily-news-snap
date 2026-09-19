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
Deployed recovery milestones:
- PR #210 / fa8d05e: bounded malformed-JSON retry and validated article redirects.
- PR #211 / 3849dde: explicit $20/day commissioning ceiling, historical charges
  and unknown reservations preserved; lower caller ceilings remain enforced.
- PR #212 / c6fcd5a: recover local image subjects, reject undersized results before
  filling the pool, and page partial pools within existing 12-request limit.
- 187 publishing tests and independent review passed before latest deployment.
- Trial 35465831225: daily passed after factual/visual repair; local held for
  imagery; $0.840751. All approved daily frames inspected. Previous engine only.
- Trial 35466789920: both held; daily exhausted factual/visual repairs and source
  alternatives, local could not retrieve articles. $0.525544; Telegram report step
  succeeded. Final engine a2804a998ea95d77d83d776f22ec6a3963303a60a50b367e664de0b1f7d276db.
- Direct retrieval of last failed local article (alyaum /6683349) succeeds from
  this environment (169090 bytes, 5378 text chars), so runner failure is not proof
  the publisher article is permanently unavailable.
- PR #213 / 4713dd9: publisher RSS fallback deployed. Substantial
  text from same allowlisted publisher, exact cached ID/URL/timestamp, at least
  500 characters and 80 words. Original article preferred. Source type/feed URL
  retained, no headlines/search snippets promoted, independent review unchanged.
  Seven focused tests passed independently; no blocking review findings.
  All 194 publishing tests and CI passed. Real feed recovered 303 words for
  the exact failed article /6683349.
- Final deployed-engine shadow/both trial 35468390489 is RUNNING.
  Engine 9df6d5279f3d1d73a2e3c0c5ddec3e9c52a2ccc895b2a73e9bff09a9896400d6.
- Final trial exposed a rubric/rendering contradiction: reviewer demanded Indic
  digits, while news_bot.ar/sanitize deliberately renders Western digits (verified
  directly: '١ من ٣' becomes '1 من 3'). Prompt-only correction permits both forms
  while still requiring the correct ordinal, total and reading order. In review.
- Repeated writer factual errors were correctly identified by the Opus reviewer.
  Configure editor, researcher, writer and visual selector to use the same stronger
  priced Opus model in separate role contexts; keep independent review and $20 cap.
  Validate model configuration and actual output before clearing posting.
No final-engine daily/local pair is cleared. No posts were made during these trials.

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
Inspect trial 35468390489 to completion; do not restart an active or held slot.
Record actual daily/local outcomes, costs, report delivery, artifact inspection
and exact posting readiness. Code fixes are deployed; both final-engine passes
are still required. No publishing during this validation run.

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
