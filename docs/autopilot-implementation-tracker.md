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
Current priority: validate updated daily/local packages in shadow mode before posting.
User moved this readiness checkpoint ahead of watchdog implementation.
Run 35459403406 on commit 6c2846819cad7e14ecff134247f5d960faa0452b:
software safeguards passed; trial was cancelled after selection-rule review.
No final daily/local pair was completed or cleared; nothing was published.
Observed first daily draft selected the previously criticized ostrich subject and
stat-heavy copy. The pipeline subsequently moved to M&S and rejected unsuitable
visual choices before cancellation; do not describe a final package as reviewed.
Cancellation confirmed via Actions. Preserve any outstanding budget reservations
and held slot state; do not clear journals or rerun this interrupted slot blindly.
This run uses mode=shadow, lane=both; it does not publish.
Readiness issue found: local discovery uses evergreen seeds and the reviewer allows
 timeless local subjects, so it does not enforce the latest requirement for a
current public-attention/news trigger on every story. Do not mark local ready
without evidence of a current trigger, even if automated review passes.
Watchdog and audience analytics have NOT been implemented.
Latest main inspected when creating this checkpoint:
93fe5f87b6b1a397a7a8e66e5e69ad68757a2d73.
That commit adds editorial/image safeguards and removes paid push-triggered runs;
do not overwrite those changes or assume earlier launch validation validates it.

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
Next focused slice: require verified current attention for local discovery and
review, and incorporate rejected-topic feedback into candidate selection.
Add deterministic tests, then run a fresh bounded shadow trial and inspect both
completed packages. Do not say ready until actual outputs meet the latest brief.
Then read current workflow, runtime, pipeline, receipt store and tests on main.
Implement stage 1 as a read-only decision module with explicit Saudi-day/deadline
handling. Verify before adding recovery mutations in stage 2.
A check running on GitHub is not an independent fallback for a GitHub outage.
Assess whether a separate scheduler is needed after the first detection slice.

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
