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
2026-09-20: user restored a $3/day shared cap for production and trials.
- Budget change: deployed in PR #215; $20 commissioning permission is superseded.
- First gradual model reduction: editor uses Sonnet 5. Researcher, writer, visual
  selector and independent reviewer retain Opus 5; no quality gate is relaxed.
- Reviewer reservation uses conservative text bytes plus 8192 tokens per locally
  resized image and the full output ceiling, rather than a whole model context.
  Official vision documentation caps these models at 4784 visual tokens/image.
- Verification: 197 publishing tests and 27 shared-budget/store tests pass.
- September 20 ledger at check: $2.261592 settled, no unresolved reservations;
  approximately $0.74 remains. No paid generation triggered by this change.
- Existing charges and unresolved reservations remain counted; no ledger reset.
- Budget holds produce a Telegram request to review costs. Any cap increase
  requires user approval; a hold alone does not establish that more money is needed.
- Trial 35469293403 completed: both packages held, no publishing. Previous
  checkpoint incorrectly called it active. No current-engine posting clearance.
- Fresh-start agreement: one NEW topic, Info + connected story, preview for user
  review before expanding automation. This fresh trial has not started.
- Watermark layout fix: deployed in PR #216 (0d6d2b0); GitHub CI passed. Crowded cards retry
  with a shorter photo area; glyph bounds enforce footer clearance. No text is
  removed. Impossible layouts return to repair rather than saving overlaps.
- Verification: 199 publishing tests passed with Almarai; actual crowded cards
  inspected with and without source footers; shared bot imports passed.
  Independent review found no blockers. No paid generation or posting.
- Known unresolved issue: image relevance/variety. Fresh preview still pending.
- Existing two-package 08:00 Riyadh schedule is unchanged. This budget change
  does not implement the fresh single-package flow or establish posting readiness.

## Milestones
| Stage | Scope | Status | Completion evidence required |
| --- | --- | --- | --- |
| 0 | Specialist editorial agents, independent review, bounded repairs, publishing journals, budget and Telegram reporting | Deployed; prior engine verified live | Launch run 35438752317 confirmed two packages / eight frames on September 19; recheck current engine before claiming readiness |
| 0a | Current-engine editorial recovery and posting qualification | Blocked; fresh preview pending | Both lanes pass shadow on the final code/model fingerprint; inspect actual frames and readiness journal |
| 1 | Detect missing, stalled, incomplete and successful daily runs | Planned; next | Deterministic tests plus read-only comparison with actual run and receipt state; no paid generation or publishing |
| 2 | Bounded safe recovery | Planned | Tests for missed run, partial delivery, concurrent run, budget exhaustion, expired package and ambiguous provider result; preserve receipt identity, review gates and budget |
| 3 | Schedule watchdog and concise Telegram incident/recovery reports | Planned | Deployed workflow and real monitor execution; deduplicated alerts; obey pause mode; document shared GitHub scheduler outage limitation |
| 4 | Observe daily reliability | Pending operational evidence | Record at least three consecutive Saudi days of both-lane outcomes, delivery receipts, alerts and authoritative daily cost; report failures honestly |
| 5 | Connect available audience metrics | Planned | Confirm provider/account access and metric definitions; real read-only metric retrieval; private storage for audience data |
| 6 | Introduce measured content optimization | Planned | Bounded recommendations from sufficient real data, editorial review preserved, comparison and rollback; never invent engagement evidence |
| 7 | Review platform/model efficiency | Planned | Compare measured output quality, delivery reliability, latency and total cost; vendor-neutral decisions |

## Immediate next action
Prepare the agreed fresh single-topic preview in a separate stage. Do not resume old story retries or expand to more paid runs.
Report milestones separately. Monitor actual cost and approved output before
recommending any budget increase; never raise the cap automatically.

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
  is historical; its $3 ceiling is restored by the latest user instruction; the temporary
  $20/day commissioning ceiling is no longer authorized.
- Keep existing Saudi Arabic style, broad audience relevance, flexible story
  length, relevant images and independent factual/visual review.
- Audience learning and sustained reliability are not yet established.
- A historical POSTED receipt is evidence of delivery at that time, not proof a
  post remains visible; account for subsequent deletions or replacements.
