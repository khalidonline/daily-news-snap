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
All current code corrections deployed; final stronger-model trial in progress.
- PR #210 / fa8d05e: bounded malformed-JSON retry and validated article redirects.
- PR #211 / 3849dde: $20/day commissioning ceiling; preserve all old charges and
  unresolved reservations, and each lower-ceiling caller's own limit.
- PR #212 / c6fcd5a: recover local image subjects, filter undersized images before
  filling the pool, page partial pools within the existing 12-request bound.
- PR #213 / 4713dd9: substantive same-publisher RSS fallback, exact ID/URL/time,
  recorded provenance, no short summaries. Real failed article recovered303words.
- PR #214 / 27c9c1f: accept both numeral glyph forms in counters while checking
  correct sequence; editor/researcher/writer/visual use the stronger priced Opus
  model in separate contexts, with independent Opus review. $20 cap unchanged.
- All 194 publishing tests and CI passed before the final model deployment.
  Independent reviews found no blocking defects; 13 runtime tests also passed.
- Trial 35465831225: prior daily pass, local held; $0.840751; frames inspected.
- Trial 35466789920: both held for content/imagery/source retrieval; $0.525544.
- Trial 35468390489: both held; repeated writer factual/visual errors and counter
  rubric contradiction confirmed; $1.481482. Operational report step succeeded.
- September19 ledger: $7.496990 settled, $0.115566 unresolved reservation retained.
- ACTIVE: shadow/both trial 35469293403 on final stronger-model configuration.
  Engine aae4c2c27caae454e71b671768447eb57bc6a782eeeccf441ea6ba27240e1064.
  New slots use Saudi date2026-09-20. No publishing during this validation.
No final-engine daily/local pair is cleared yet. Do not claim posting readiness.

## Milestones
| Stage | Scope | Status | Completion evidence required |
| --- | --- | --- | --- |
| 0 | Specialist editorial agents, independent review, bounded repairs, publishing journals, budget and Telegram reporting | Deployed; prior engine verified live | Launch run 35438752317 confirmed two packages / eight frames on September 19; recheck current engine before claiming readiness |
| 0a | Current-engine editorial recovery and posting qualification | Deployed; validation in progress | Both lanes pass shadow on the final code/model fingerprint; inspect actual frames and readiness journal |
| 1 | Detect missing, stalled, incomplete and successful daily runs | Planned; next | Deterministic tests plus read-only comparison with actual run and receipt state; no paid generation or publishing |
| 2 | Bounded safe recovery | Planned | Tests for missed run, partial delivery, concurrent run, budget exhaustion, expired package and ambiguous provider result; preserve receipt identity, review gates and budget |
| 3 | Schedule watchdog and concise Telegram incident/recovery reports | Planned | Deployed workflow and real monitor execution; deduplicated alerts; obey pause mode; document shared GitHub scheduler outage limitation |
| 4 | Observe daily reliability | Pending operational evidence | Record at least three consecutive Saudi days of both-lane outcomes, delivery receipts, alerts and authoritative daily cost; report failures honestly |
| 5 | Connect available audience metrics | Planned | Confirm provider/account access and metric definitions; real read-only metric retrieval; private storage for audience data |
| 6 | Introduce measured content optimization | Planned | Bounded recommendations from sufficient real data, editorial review preserved, comparison and rollback; never invent engagement evidence |
| 7 | Review platform/model efficiency | Planned | Compare measured output quality, delivery reliability, latency and total cost; vendor-neutral decisions |

## Immediate next action
Inspect trial35469293403 to completion, including Saudi-date2026-09-20 journals.
Do not cancel/restart working or held slots. Inspect approved artifacts and record
actual costs, operational report delivery and final readiness. The schedule remains
05:00UTC /08:00Riyadh; live falls back to shadow until both final-engine lanes pass.

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
