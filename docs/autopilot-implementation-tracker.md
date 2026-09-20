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
  review before expanding automation. An assistant-prepared fresh preview is now ready; no automated qualification run.
- Watermark layout fix: deployed in PR #216 (0d6d2b0); GitHub CI passed. Crowded cards retry
  with a shorter photo area; glyph bounds enforce footer clearance. No text is
  removed. Impossible layouts return to repair rather than saving overlaps.
- Verification: 199 publishing tests passed with Almarai; actual crowded cards
  inspected with and without source footers; shared bot imports passed.
  Independent review found no blockers. No paid generation or posting.
- Known unresolved issue: image relevance/variety. Fresh preview ready for user review.
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
Michelin preview approved and published: all three cards confirmed POSTED. Saudi writing standard merged in PR #218. Next: check remaining daily budget, then one fresh automated review-only package within the $3/day cap; no old story retries.
This is an assistant-prepared content/design preview, not an automated agent pass. Do not resume old story retries or expand to more paid runs.
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

## Fresh preview checkpoint — 2026-09-20
- Topic: Michelin, from tyre company to restaurant guide.
- Current trigger: Asharq Al-Awsat, “أطباق من أجلها يسافر الذواقة حول العالم”,
  published 20 September 2026, https://aawsat.com/node/5320313.
- Facts: https://en.wikipedia.org/wiki/Michelin_Guide; first guide 1900,
  restaurant stars 1926 and three-star hierarchy 1931.
- Delivered michelin-fresh-preview.pdf: one Info + two connected story cards,
  then a separate review-notes/source page (not a Snapchat card).
- Images: Commons 117592989 (CC0, modern Michelin tyre display),
  128634934 (public domain, 1900 guide cover), 49390080 (CC0, company mascot).
  Full subjects preserved in photo windows; provenance links in PDF.
- Actual final PDF pages inspected: Almarai/light, numbered 1 of 2 and 2 of 2,
  no missing image or watermark/text overlap observed.
- No paid model API calls; no Telegram or Snapchat publication.
- Assistant-prepared preview only. Independent automated review/readiness remains
  outstanding; do not record this preview as a shadow pass or posting clearance.

## Saudi wording revision checkpoint — 2026-09-20
- User approved the richer Saudi story wording with the exact phrase «دليل مجاني».
- Applied that wording to all three Michelin cards; retained approved design and images.
- Updated preview specification and regenerated the PDF; visually inspected all three cards for readability, numbering and footer clearance.
- Revised PDF delivered for final visual review. No paid model calls, production code changes or publishing in this step.
- Next: user reviews revised cards before publication; automated agent qualification remains outstanding.

## Approved Michelin publication checkpoint — 2026-09-20
- Owner reviewed and approved the revised three cards.
- Exact media and hash-checked manifest committed at approved/michelin-20260920/manifest.json.
- Automatic approval review blocked the publishing workflow submission: it requires explicit confirmation of immediate public Snapchat publication beyond approval of the cards.
- No successful publishing submission or delivery receipt in this step. Await explicit publish-now confirmation; do not duplicate or regenerate media.

## Michelin delivery completed — 2026-09-20
- User explicitly confirmed immediate Snapchat publication.
- Approved Snapchat API run: https://github.com/khalidonline/daily-news-snap/actions/runs/35497827987.
- All three approved cards confirmed POSTED in order on @executivesaudi.
- Durable receipt: snapchat-api-state/api-receipts/cee93bdd6d139a58e7240433e143b4ba2ca5c313034c850579c67d6da07ca229.json.
- Exact approved media reused; no model generation or paid model calls for publication.
- Manual approved delivery is complete. This does not qualify autonomous generation or change the $3/day budget.

## Info footer identity fix — 2026-09-20
- User requested the same footer brand logo as story cards after reviewing the published Info card.
- PR #217 merged (b58aed50f626f07cbc32138acbdb478640700e1e): closing logo renders independently of source footer text; uses existing reserved space.
- Updated Michelin Info preview rendered and visually checked. Six existing preview tests passed offline; no paid generation.
- Future Info renders include the footer logo. Published Michelin media was not replaced or reposted.
- Saudi writing-standard implementation remains the next editorial task.

## Saudi writing standard deployed — 2026-09-20
- PR #218 merged: 539fab1c5607eeb3d654bc26c84ea3099a070db1.
- Shared voice: everyday Saudi wording, including «دليل مجاني», with proper names and factual uncertainty preserved.
- Writer: useful subject-first Info plus documented, connected story beats; no invented motives, filler or repetitive closing lines. Michelin is a style example only, not evidence for new subjects.
- Reviewer: explicit language and over-compression criteria feed existing blocking checks.
- Body ceiling increased from 240 to 320 for optional context; ceilings are not targets. Approved Michelin bodies (198/233/218 chars) already fit the former cap; extra headroom is not a claim that the former cap alone caused weak writing.
- Verification: 103 autopilot tests, 22 focused pipeline/policy tests including new boundaries and rejection checks, two footer-layout tests; CI 35498377169 passed.
- No paid generation, budget changes or publishing in this step. Actual output quality and 08:00 autonomous posting remain unqualified.
- Next checkpoint: reconcile current remaining budget, run one fresh automated review-only package if affordable, inspect its actual cards and review receipt. Do not regenerate Michelin or bypass quality gates.

## Fresh trial preflight — 2026-09-20
- User authorized one fresh automated review-only package after writing-standard deployment.
- Authoritative cost-ledger/daily/2026-09-20.json: $2.261592 settled, no outstanding reservations; $0.738408 remains under the active $3 cap.
- Held before any paid call: current five-role cycle needs at least $1.2288 of worst-case output/image allowance for three cards, even before textual input (Sonnet editor 8192 output tokens, three Opus roles at 8192 each, Opus reviewer at 16384, three 8192-token image allowances). This is reservation headroom, not predicted actual spend.
- No new workflow dispatched; no paid model calls or publishing. No budget increase requested or applied.
- Next: one fresh daily shadow trial with adequate available daily headroom. Do not treat this note as a scheduled automation or claim 08:00 posting is qualified.

## Authorized fresh trial started — 2026-09-20
- User authorized additional budget and continuation. Temporary total shared cap: $5 for daily shadow mode on September 20 only; regular cap remains $3 for other modes/dates.
- Workflow guard committed as 755becebbcfd6fae1517db5e0befd0e736429a9f; date evaluated in Asia/Riyadh. No ongoing budget increase.
- Started run https://github.com/khalidonline/daily-news-snap/actions/runs/35498778289 with mode=shadow, lane=daily on current main. No Snapchat publishing.
- Opening ledger balance: $2.261592 spent, zero reserved. Maximum additional spend under temporary cap: $2.738408.
- In progress: monitor THIS run and inspect its final package/review/cost. Do not launch another run or revisit old trials.

## Fresh trial result — 2026-09-20
- Run 35498778289 completed held/failed. Trial cost $0.897525; authoritative daily total $3.159117, no reservations outstanding, $1.840883 below today's temporary $5 ceiling.
- One Wembley draft reached independent pixel review; rejected for wrong-event branding, poor image quality and misleading sporting-event illustrations. Repairs could not find a full appropriate image set.
- Subsequent Mourinho/Simeone candidate also lacked relevant portraits/event imagery; selected results included unrelated art, restaurants and other sports. It was not approved.
- Terminal status BudgetBlocked after the last writer step. The current pipeline stores only the exception class; the exact cause is NOT established and must not be described as exhausting the $5 cap. Earlier calls above $3 confirm the temporary cap took effect.
- Next implementation: retain safe structured budget failure diagnostics and improve image feasibility before writing. Do not spend on another generic rerun or raise budget again without evidence.
- Current trial slot: autopilot-2026-09-20-daily-shadow-aa09930baddb0afc. Artifact 10600883624 retains rejected output. No publication; no current-engine qualification or 08:00 promise.

## Budget diagnostics and image preflight deployed — 2026-09-20
- PR #219 merged: ba988515334f2c088e4217a074e2e3a950e62bd7; final GitHub offline checks passed.
- Budget reservation failures now retain safe codes, actual configured cap, requested reservation and charged balance; agent role is attached. Saved state, summary and report carry these diagnostics without raw exception/provider text. Unknown historical cap is not reported as $3.
- Preflight now requires canonical subject words in title/description, normalizes accents, and does not treat partial-name unrelated art/restaurants as subject photos. Licensing/dimension checks remain, followed by mandatory independent pixel review.
- Removed cross-query result-cache aliases that could contaminate broader subject searches. Exact search responses and repeated identical queries remain cached.
- Five targeted regression tests and ten media recovery tests pass; full CI passed after replacing obsolete cross-query-cache expectation. One legacy test_daily_budget workflow-presence assertion still fails against the unchanged read-only cloud audit workflow; budget unit tests otherwise passed.
- No paid trial or publishing during this change. Historical BudgetBlocked cause is still unknown; diagnostics are instrumentation, not proof that it is fixed. Preflight may reject genuine images whose metadata lacks full subject names; it does not prove relevance or provide new image suppliers.
- Next: reconcile remaining approved budget, then one fresh daily shadow trial on this engine; assess actual selection, images, Saudi narration and final review. Do not resume the rejected prior-engine output.
