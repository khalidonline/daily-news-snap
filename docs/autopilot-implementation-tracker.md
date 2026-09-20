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

## Post-fix fresh trial started — 2026-09-20
- User authorized next review-only trial after PR #219.
- Run 35499984096, main 6075e04baaa19c367aaf07fa6113c0c8cf35cea9; mode shadow, daily only. No publication.
- Opening settled spend $3.159117; $1.840883 remains under today's approved temporary $5 cap. No further increase.
- Monitor this run to completion and inspect its final review plus any structured budget diagnosis. Do not restart the previous engine's trial.

## Post-fix trial completed — 2026-09-20
- Run 35499984096 completed held: no_package_passed_review. All four selected candidates failed insufficient_subject_visuals_before_drafting.
- Only editor ran: cost $0.060626. Daily settled total $3.219743; no outstanding reservations. $1.780257 remains under today's temporary $5 cap.
- No research/writing/rendering/final review or publication occurred. Early screening prevented additional spend, but did not produce publishable content.
- Last selected research query was 'Saudi Arabia national football team squad Dawnis', showing the editor still emits descriptive/noncanonical search queries. This makes exact-word metadata screening overly restrictive for such queries; not evidence that no usable photos exist.
- Next implementation should address canonical subject resolution and image-source coverage together. Do not weaken independent pixel review or retry the same pool blindly. Prior budget cause remains unproven; this trial had no budget failure.
- Automatic 08:00 posting is still not qualified. No additional budget increase.

## Subject resolution and image-pool fix deployed — 2026-09-20
- PR #220 merged; final GitHub offline checks passed.
- Research resolves only a unique retrieved encyclopedia title matching the query exactly or a leading phrase of at least two words and 60% of query tokens. Retains source ID; unrelated/ambiguous results are not promoted.
- Renderer uses that resolved subject for image preflight and fallback. No model-selected arbitrary URLs or unverified alias substitution.
- Preflight filters irrelevant image metadata before filling the bounded pool, allowing later pages to contribute. Filtered caches are separate; exact API responses remain reusable. Same licensing/dimension/pixel-review safeguards and request bounds.
- Four new unit/integration tests plus existing diagnostics, media and recovery tests passed; full CI passed. No paid calls or publication.
- Next: reconcile approved remaining budget and run one new-engine daily shadow trial. Actual image availability and output quality remain unproven; no 08:00 qualification. No new image supplier has been added.

## Post-resolution trial started — 2026-09-20
- User authorized next trial after PR #220. Run 35500652285: daily, shadow, current main. No publishing.
- Opening settled balance $3.219743; $1.780257 remains under today's approved $5 shared cap.
- Engine 639f0b653e5396cfcd9402609039df9d1fc0af0d46b44aa42daa8fc5026474e3. Monitor this single run and persist its outcome before any further work.

## Post-resolution trial result — 2026-09-20
- Run 35500652285 held: no_package_passed_review. Four candidates again failed insufficient_subject_visuals_before_drafting; editor was the only paid role.
- Trial cost $0.066626. Authoritative settled daily total $3.286369; no reservations outstanding. No writing, generated cards, final review or publication.
- Subject-resolution/paging changes have NOT demonstrated improved live coverage. Do not claim image sourcing is solved or schedule qualified posting.
- Next is an unpaid source-retrieval/rights audit using actual queries and returned records. Preserve query, canonical resolution, raw count, license rejection count, size count and subject-match count to distinguish retrieval gaps from overly strict filters.
- Two consecutive preflight holds justify reconsidering source acquisition/provider coverage, rather than another generic paid rerun or speculative prompt patch. No further budget increase.

## Unpaid source audit complete — 2026-09-20
- Evidence and findings: docs/audits/2026-09-20-images/README.md and raw metadata.
- Combined rivalry query: zero files. Individual-name samples: 30 files, 25 large enough, 28 metadata matches, zero passing all current gates.
- Principal sample exclusions: unsupported BY-SA/BY 2.0, public-domain image size, and one BY 4.0 personality flag. No connectivity failures in this probe.
- Next: explicit separate verified subjects plus correctly implemented CC BY 2.0 attribution/delivery, then unpaid image-only feasibility check before another paid generation run. Do not relax all restrictions or infer provider replacement is necessary.
- Audit cost $0 AI; no production/publishing/budget changes. Previous unexplained budget hold remains separate.


## Separate subjects and CC BY 2.0 implementation — 2026-09-20
- PR #221 adds independently verified one/two-subject searches and exact-version CC BY 2.0/4.0 credits, supplied notices/source links, and same-video attribution delivery safeguards.
- Free live production-pool probe: Mourinho 2 eligible photos, Simeone 0. Both Mourinho files downloaded/decoded and rendered complete credits; combined credits fit. No paid AI or publication.
- Evidence: docs/audits/2026-09-20-cc-by-2/README.md, results.json, production-pool.json.
- Existing 210 v2 tests and 15 focused tests passed locally. Final PR CI passed and PR #221 merged.
- This rivalry package remains held for missing Simeone imagery. Next: an adequately sized, verified, properly licensed Simeone source or another image-feasible angle, before fresh paid generation. No automated 08:00 qualification or budget change.


## Fresh multi-source recovery merged — 2026-09-20
- PR #222 merged after final CI passed (offline tests, actual layout checks, and isolated container).
- Production preflight now searches Commons, dedicated Commons collections and public Flickr photo pages, validates source identity/license and actual downloads, and attempts original renditions before paid drafting. Bounded request counts/deadline; duplicate originals rejected across providers.
- No permanent local photo collection. Preflight retains metadata/hashes only; render sources use temporary files removed on success/failure. Final review cards/video remain normal workflow artifacts.
- Free live coverage: Jeddah 5 candidates, iPhone 3, date palm 2 (Commons + Flickr), Saudi coffee 1 (Flickr), Simeone 0. Counts are retrieval/rights/metadata candidates, not final visual approvals.
- Initial coffee false positives (market portrait and Swedish cafe sign) were found during review and excluded with a proximity filter. Final coffee query retrieved the specifically titled Saudi Coffee photo. Evidence: docs/audits/2026-09-20-multisource/README.md and per-topic JSON.
- Openverse returned HTTP 403/timeouts; no dependency, access bypass, subscription or account was added. Flickr source failures remain possible and recovery continues to another stage.
- 225 v2 tests passed locally before the final regression; 21 focused tests including it passed, followed by final full PR CI success. AI cost $0; no publishing or budget changes.
- Next checkpoint: expand verified source/alias coverage or implement adaptive small-portrait layouts, then a fresh reviewed package. Current Simeone/coffee/date-palm pools do not meet the three-image preflight target. No automatic 08:00 qualification and no paid retries on unchanged inadequate pools.


## Outcome checkpoint: one complete fresh package — 2026-09-20
- Owner redirected work from isolated improvements to a complete reviewable package. Do not start another enhancement project during this checkpoint.
- Run 35503159394 started on main 1f44e2ca53b626a15ee8bf3d69a0297b479167db: daily lane, shadow/review only. No publishing authorized until owner reviews final frames.
- Opening settled daily AI cost $3.286369; no reservations. $1.713631 remains under the already approved $5 shared trial cap for today. No budget increase.
- Checkpoints: (1) current trigger and sufficient visuals; (2) Saudi-language Info + connected story, design and quality review; (3) finished frames, actual incremental cost, and owner approval.
- If a candidate remains blocked, move to another strong current candidate. Success is the finished package, not another technical fix.


### Outcome delivered: assisted Saudi food package
- Fresh automatic run 35503159394 held before writing: all four candidates failed subject resolution. This is not a successful unattended cycle.
- Delivered an assisted review package based on Al Yaum article 6683413, published 20 September 2026: one Info card, two connected Story frames, and one complete CC BY 2.0 credits frame. Saudi Arabic; existing light Almarai design and footer logo.
- Final PDF uses decoded frames of the verified 1080x1920 H.264 video, 45 seconds. All four frames visually inspected; readable, no clipped text. Three distinct archival subject photos, no paid image generation. Raw source images downloaded temporarily and discarded.
- Run cost $0.066122; settled daily API cost $3.352491. No further paid production calls for assisted completion. No budget increase.
- Package content, source metadata, image provenance, and exact video/frame hashes: docs/audits/2026-09-20-food-review/package.json.
- Status: finished assisted package awaiting owner review; NOT published. Next: owner reviews this package; separately, resolve subject matching as the concrete blocker before demonstrating repeated unattended cycles. Do not claim 8am automatic posting is ready.


### 20 September: review-only sources deployed; fresh trial active
- Owner deleted the accidentally published F-35 source card. Do not republish it or the package.
- PR #223 merged as fbae9e42bfb8ece1de61ef010cea0c57fdab28d7 after 231 v2 tests and GitHub offline/container checks passed; independent review found no blockers.
- Review always includes sources. Snapchat selects editorial frames only; untyped manual manifests and old source-card videos stop before upload.
- CC BY remains review-supported, not publicly publishable with its attribution removed. Automatic public selection uses PD/CC0 until visible attribution is designed and reviewed.
- Verified Wikipedia aliases now resolve exact redirects (Saudi cuisine → Saudi Arabian cuisine). Real free image probe still found zero suitable cuisine images: do not label the entire image-recovery problem solved.
- Fresh daily SHADOW run 35511704697 started. No new public posting in this step. Opening daily settled $3.352491; existing date-limited $5 trial cap, no increase.
- Detailed implementation and full-suite legacy failures: docs/audits/2026-09-20-review-only-sources.md.
- Next: inspect actual trial result, cost and images; fix concrete remaining blockers before scheduling a three-day reliability test. 8am unattended publishing is not confirmed.


### Fresh trial 35511704697 outcome
- HELD, no package written/designed and no public post. This is NOT unattended success.
- Four candidate attempts: two `insufficient_subject_visuals_before_drafting`, two `unresolved_editorial_subject`.
- The Shawshank Redemption and PepsiCo reached multi-provider visual search; new canonical resolution works for some topics. Remaining abstract subject example: `Aging and metabolism` (not a concrete entity).
- Actual incremental cost $0.062660; verified settled daily total $3.415151. No additional rerun and no budget increase.
- Completed checkpoint: review/public source separation is deployed and tested. Remaining stage: concrete visual subject planning plus sufficient eligible public imagery. Strict no-source-card publication currently excludes CC BY; public attribution requires a reviewed non-card solution or alternative licensed/public-domain assets. Do not weaken identity or license checks just to obtain a pass.
- Next implementation should address these concrete failures before another paid full-cycle attempt. The three-day reliability trial has not started. User wants gradual checkpoints; do not repeat the completed separation work or claim 8am readiness.

### Small follow-up: concrete subject naming
- Only the two unresolved subjects from run 35511704697 examined: Bisht and Aging and metabolism.
- Explicit disambiguator instructions, bounded same-name contextual resolution and per-subject diagnostics implemented; 12 targeted tests pass.
- Corrected Bisht (clothing) lookup verified against live source. Abstract compound remains rejected, without replacing it with unrelated stock imagery.
- No paid generation, new package run, stories.txt review or broad local test suite.
- Next remains image diversity. Do not claim the live editor or complete package has passed on the strength of these tests.

### Small follow-up: public image pool starvation
- Owner: assistant. Scope: image sourcing only; no stories.txt, paid package run or posting.
- Found and fixed a collector/renderer mismatch: attribution-required review assets filled the five-image pool before public filtering. Production now applies public eligibility before the pool/download caps.
- Public recovery skips the current CC-BY-only Flickr adapter; review sourcing retains it. Existing request and download limits unchanged.
- 25 focused tests passed; independent review found no blockers. Details: docs/audits/2026-09-20-public-image-pool.md.
- Public image availability remains an open gate. Next: resolve eligible visual supply before a fresh paid package; do not claim autonomous publishing readiness.

### Small follow-up: Flickr CC0 discovery
- Owner: assistant. Added a public-compatible second source through existing Flickr adapter: CC0 search plus independent photo-page verification. Default review CC BY remains supported.
- Source, subject, dimension and deduplication checks retained. No paid calls, story archive scan or posting.
- 17 focused tests passed; independent review found no blockers. Audit: docs/audits/2026-09-20-flickr-cc0.md.
- Next gate: confirm a candidate has enough distinct and relevant visual options, then one fresh shadow package. No unattended-success or schedule-readiness claim.
- Live outcome: PepsiCo now reaches 3 downloaded eligible assets (previously 2); all factory photographs, so perceptual diversity/editorial fit still needs review. Flickr CC0 returned 3 metadata-verified Jeddah results and 0 Shawshank results.

### Fresh shadow checkpoint — 20 September, 16:29 Riyadh
- Owner: assistant. Run 35513642131, daily SHADOW on 48c9fe784de0f6abf7b9471e041cadf98af56573; one fresh package attempt, no Snapchat publication.
- Opening settled daily cost $3.415151; no pending reservations. Existing date-limited $5 daily-shadow cap applies; no budget increase.
- Active: fresh discovery → editor → visual feasibility → research/writing/design/review if gates pass. Track this run only; no stories.txt backlog scan or repeated runs.
- Outcome pending. Do not claim readiness until the actual package, sources separation, visual/editorial review and cost are checked.

### Fresh shadow 35513642131 — final outcome, 16:31 Riyadh
- HELD after three unresolved_editorial_subject rejections. No research/writer/visual/reviewer calls, rendered cards, publication or new readiness pass. Existing workflow's 242 offline checks passed; operational generation did not.
- New concrete editorial integrity defect in final candidate: source ID f178695245978b9f/title about Yemeni army operations west of Taiz (https://aawsat.com/node/5320469) was paired with editor angle about Saudi footballer Musab Al-Juwayer's apology. Wikipedia lookup for Musab Al-Juwayer returned no retrieved titles. Do not describe this as only an image-availability failure.
- Candidate ID membership is currently checked, but it does not establish semantic agreement between the source and selected angle/subject. Next small implementation: preserve/validate source-to-angle identity before downstream work, and diagnose unresolved names for this run without another paid full trial. Do not weaken subject matching or merely add another image provider.
- Only one paid editor call: $0.061214. Verified settled daily total $3.476365; $1.523635 remains within today's existing $5 shadow cap. No budget increase and no repeated run.
- State: snapchat-api-state/api-receipts/autopilot-2026-09-20-daily-shadow-8548eb751b287677.json. Full automatic readiness remains unconfirmed.

### Small follow-up: source-to-angle binding
- Owner: assistant. Added exact source-title and per-subject verbatim evidence validation before research/image planning. Invalid binding rejects that candidate and continues the bounded ranking.
- Every rejection now preserves candidate ID and source title in audit; no need to inspect older story archives to understand which candidate failed.
- 35 focused tests passed; no paid run or publishing. Audit: docs/audits/2026-09-20-editor-source-binding.md.
- Limit: lexical binding does not prove translated entity identity or semantic truth; existing source/reviewer gates remain. Next: diagnose unresolved names in run 35513642131 before another paid trial.

### Small follow-up: source-language subject recovery
- Owner: assistant. Diagnosed only run 35513642131: Bisht and Red Sea Global already resolved; second subjects Al-Ahsa and the medical group failed English lookup. Football candidate had invalid source binding and is not a recovery target.
- Added exact Arabic source-name/official-redirect fallback after English failure, gated by #227 binding validation. Preserve canonical Arabic identity and language-scoped source IDs. No fuzzy replacement or forced English alias.
- Free probes resolved الأحساء and مجموعة الدكتور سليمان الحبيب للخدمات الطبية → مجموعة الحبيب الطبية. 20 focused tests passed; no paid package or posting.
- Audit: docs/audits/2026-09-20-native-subjects.md. Next: one fresh shadow package within approved budget; image availability and live editor performance remain unproven.

### Combined fresh trial — 20 September, 17:34 Riyadh
- Owner: assistant. Run 35516891749, daily SHADOW on 6ffd9c31f4c6213135905b4862a215a10b88782a, combines source binding, Arabic exact-name recovery and public image sourcing. No Snapchat posting.
- Opening settled daily cost $3.476365; no pending reservations. Remaining $1.523635 within today's existing $5 shadow cap. No budget increase.
- One run only; outcome pending. Follow candidate audit, package review and exact final cost before claiming success. No archive scan or extra paid rerun.

### Combined run 35516891749 — final outcome, 17:36 Riyadh
- HELD before research/writing/design; no cards or post. Only editor was charged: $0.072170. Daily settled total verified at $3.548535; no automatic rerun or budget increase.
- Bisht and Mohamed Salah passed source binding/subject resolution, then failed public image feasibility. Bisht 0 accepted; Salah 1. Provider logs show rights rejection dominates. Exact parenthetical subject metadata also rejects 2 Bisht results; no claim that all image availability failures are licensing alone.
- Medical-group and Luke Littler candidates failed editor_subject_mention_not_grounded. Final Littler candidate has the correct BBC title and verbatim English quote, but Arabic angle uses ليتلر instead of exact Luke Littler. The literal mention-in-angle requirement creates a false rejection for translated/shortened names. Do not treat that as source fabrication or weaken exact quote-to-source checks.
- Next bounded correction: separate verbatim source-name grounding from translated Arabic presentation; preserve source identity verification. Broader remaining decision: public-compatible image supply versus a reviewed attribution solution. PD/CC0-only coverage is insufficient for these actual subjects; repeated provider searches/full paid retries are not a solution.
- Full package, visual review and autonomous readiness remain unproven. Do not start another full paid trial until these concrete gates are addressed. State: api-receipts/autopilot-2026-09-20-daily-shadow-7b28546baf6d36e3.json on snapchat-api-state.

### Small follow-up: allow Arabic presentation of source names
- Owner: assistant. Corrected #227 false rejection reproduced by Luke Littler → ليتلر in run 35516891749.
- Exact title/quote/source mention checks remain. Angle/why_now may translate or shorten the name; independent factual/current_attention review assesses semantic identity.
- 32 focused tests passed. No paid generation or posting. Audit: docs/audits/2026-09-20-translated-editor-names.md.
- Remaining blocker: public-compatible image supply/attribution. No paid full retry until that is addressed; source cards remain review-only.

### Attribution delivery feasibility — 20 September
- Owner: assistant. Read current Bundle platform field documentation (https://info.bundle.social/api-reference/platform-parameters): Snapchat STORY lists media upload/type; text/description are Spotlight-only, and no Story attachment-link field is documented. Direct raw OpenAPI fetch returned HTTP 403, so undocumented link support is unverified, not declared impossible.
- CC BY 2.0 section 4 requires license URI and reasonable author/title/source attribution; a private review-only source card is not a public attribution delivery mechanism (https://creativecommons.org/licenses/by/2.0/legalcode).
- No undocumented payload fields, public attribution page, provider purchase, code change or paid production trial was attempted. Existing PD/CC0 publication gate stays in place.
- Read-only Flickr BY probe for Mohamed Salah returned a different person (worker Medhat Mohamed Salah); not a footballer photo, not accepted or used as a mockup. Names and licensing alone do not establish relevance.
- Concrete design decision pending owner preference: retain review-only sources card; optionally place an on-card photo-credit strip only for attribution-required photos, carrying creator, supplied title, source/license URI and modification notice as applicable. This changes the owner's prior preference against visible photo-source labels, so do not enable it without that choice. Alternative: obtain a supplier agreement explicitly permitting the intended editorial Snapchat use without visible credit; no price/access/waiver is yet confirmed.
- Next implementation only after that presentation/licensing choice. No additional paid package runs while public imagery remains blocked.


### No-visible-credit supplier checkpoint — 20 September
- Owner explicitly declined the proposed visible credit strip ("لا مايحتاج"). Keep the sources card in review only; do not treat this as permission to remove required attribution.
- Completed read-only provider feasibility check; no AI spend, source-photo storage, supplier purchase, publication, or production code changes.
- Pexels general license permits use without attribution (https://www.pexels.com/license/). Its API separately requires a prominent Pexels link and credits when possible, plus an API key (https://www.pexels.com/api/documentation/). General-license permission alone does not establish this automated publishing integration's compliance.
- Pixabay general license permits adapted use without attribution, subject to other rights/restrictions (https://pixabay.com/service/license-summary/). API docs request source identification in search results, require 24-hour request caching, prohibit systematic mass downloads and permanent hotlinking, and require downloading selected images to the server (https://pixabay.com/api/docs/). Temporary rendering downloads may fit the owner's no-permanent-photo-library preference; this has not been implemented or supplier-confirmed.
- Unsplash API terms sections 6/9 require hotlinking/download event reporting and application attribution (https://unsplash.com/api-terms). Do not classify all API output as attribution-free based on the ordinary image license, or claim that final-export attribution is conclusively settled.
- Actual public search pages for Mohamed Salah were inspected: https://www.pexels.com/search/mohamed%20salah/ and https://pixabay.com/images/search/mohamed%20salah/. Their headline result counts do not prove footballer coverage. Pixabay exposed broad Muhammad/religious tags; neither probe yielded a verified accepted footballer asset. This is NOT proof that the catalogs contain no Salah photos. No authenticated API coverage test was performed.
- Decision: none of these sources is yet demonstrated to solve the actual celebrity-image blocker; do not buy a subscription or add a production adapter merely from catalog size or license-summary wording.
- CANCELLED by subsequent owner instruction: do not reuse the same image within a story. Earlier reuse permission does not authorize within-story repetition. Do not lower distinct-image requirements or implement the proposed one-photo fallback.
- Full unattended production remains unproven. Last verified daily spend remains $3.548535; no additional paid trial in this checkpoint.


### Distinct-image requirement retained; Bisht feasibility checkpoint
- Owner instruction: no reuse of the same photograph within a story. Cancelled the proposed one-photo/repeated-crop fallback in this tracker. No production-code change was made.
- Read-only live adapter probes for "Bisht", "بشت", and "Bisht haswbstatement:P275=Q6938433" all returned request_failed in this execution environment. These are transport failures, NOT zero-image results and NOT evidence of a GitHub production outage. Initial limit=10 probe was rejected locally by the adapter; corrected to supported limit=5 before the requests.
- Public source pages were independently accessible. Category:Bisht is a Russian village (https://commons.wikimedia.org/wiki/Category:Bisht); Category:Bisht_(clothing) is the correct garment (https://commons.wikimedia.org/wiki/Category:Bisht_(clothing)). Do not fix canonical-name matching by blindly dropping the disambiguator from collection selection.
- Correct garment category lists four files: a 427x561 historical portrait, two versions of the same official portrait, and one sewing photograph. Inspected all four file pages. Official portrait versions and sewing photo explicitly carry CC BY-SA 4.0; historical portrait is below current minimum dimensions and has mixed derivative-license notices. This category does not supply three distinct currently eligible images; changing text matching alone does not resolve this sample.
- No new images accepted, downloaded or published; no paid AI or full workflow dispatch. Do not report sourcing as fixed.
- Remaining work is actual licensed image supply for strong current subjects. A supplier integration must demonstrate distinct relevant samples and permission for this no-visible-credit publishing use before production activation. Preserve public-source-card exclusion and current distinct-image checks.


### Additional-source search: first verified new supplier — 20 September
- Owner requested continued search, not stopping at the existing providers. Distinct images within each story remain mandatory; source cards remain review-only.
- THE MET: live API search and individual object endpoints worked without a key. Reviewed official Open Access policy, API docs and API terms: https://www.metmuseum.org/policies/image-resources ; https://metmuseum.github.io/ ; https://www.metmuseum.org/policies/terms-and-conditions . Only object-specific Open Access/public-domain images qualify; unrestricted metadata alone is not an image license.
- Tested nine object records from garment/coffee searches. Five garment records had isPublicDomain=false and empty image URLs and were rejected. Four records had isPublicDomain=true and primaryImage; downloaded only into memory, decoded with Pillow, computed hashes, and discarded bytes. No permanent photo files.
  - 86273 Abaya Cloak; Syria, late 19th–early 20th century; 1400x2402; 220174 bytes; SHA256 27010d05dd308e4fb0a5d9c3c4cbcb757bc85e0e8125c6ae8afc234e952a114e. https://www.metmuseum.org/art/collection/search/86273
  - 875581 Coffee Pot on Stand (part of a service), 1805; 3000x4000; 1580371 bytes; SHA256 6c76343cfa6cae84b1b70329474f766ba83f1caebe38e1882c1ea3e1dac0e85f. https://www.metmuseum.org/art/collection/search/875581
  - 443173 Coffee Pot, attributed to Turkey, 1809–60; 2995x4000; 1006222 bytes; SHA256 c332b16765f2b1895f48274a7b714e5169cfb7009f9ad840aba4ded953a48c64. https://www.metmuseum.org/art/collection/search/443173
  - 444566 Coffee Pot, attributed to China/Yarkand, probably 19th century; 3000x4000; 1594685 bytes; SHA256 001a1372ca184fbd6653cffe78295ff34ebca14197ea1476a09378ad26b6f4f4. https://www.metmuseum.org/art/collection/search/444566
- These are four distinct object IDs and byte hashes; download/decoding and rights metadata are verified, NOT a final pixel/editorial review or a complete story. Do not mislabel Syrian/Turkish/Chinese objects as Saudi, force an old object into today's event, or count alternate photographs/crops as different subjects merely to satisfy variety.
- Exact "bisht" search returned zero; broader museum catalog terms "abaya"/"Arab cloak" found records. This demonstrates a useful historical/cultural source, not resolution of current Saudi-bisht or celebrity image supply.
- API migration: current official docs deprecate /v1/search with retirement October 1, 2026. New /v1.1/search with limit=3 and offset=0 tested HTTP200 and returned 3 object IDs. Use bounded v1.1 search in any new adapter; retain v1 object-detail endpoint. Do not implement on deprecated search.
- SMITHSONIAN: https://www.si.edu/openaccess/faq explicitly permits CC0 reuse without attribution, including social-media bots; individual asset rights must be CC0. Official GitHub README is reachable and directs bulk metadata to AWS, while public search access was unsuccessful here. No verified subject image/API integration yet; no bulk download undertaken. Useful second candidate after actual topic-sample validation.
- CLEVELAND: https://www.clevelandart.org/open-access explicitly confirms CC0/no-attribution and no-key API. Two direct API probes (bisht, coffee) returned HTTP403; not bypassed. Docs are accessible but source retrieval is not established in this environment.
- NASA: https://www.nasa.gov/nasa-brand-center/images-and-media/ asks source acknowledgement and distinguishes third-party copyrighted assets; not blanket-qualified as no-credit.
- GETTY: https://www.gettyimages.com/eula (April 2026) requires editorial credit; additionally restricts AI use of editorial imagery/metadata absent express authorization. A standard paid subscription does not satisfy this project's no-visible-credit plus automated visual-review requirements. A tailored agreement must explicitly cover both before activating the existing Getty experiment.
- Library of Congress public free-to-use page returned403 here; no blanket rights/source availability claim.
- Decision/next bounded implementation: The Met is the first new source demonstrated through actual rights records and successfully decoded distinct images. Add a narrowly scoped, bounded, source-verified adapter for historical/cultural objects, retaining object geography/date, official source links, strict isPublicDomain=true, image-size checks, identity checks and duplicate protections. Do not route modern-person image searches to museum substitutes or claim general topic coverage. Production adapter NOT implemented in this search checkpoint.
- Cost: $0 paid AI and no subscriptions, generation runs, purchases or public posts. Search checkpoint complete with concrete source evidence; autonomous posting remains unproven.

### Met adapter implementation and additional-source checkpoint
- Owner authorized connecting The Met and continuing source research. Implemented bounded v1.1 search (3 object records), exact official-image hosts, strict boolean public-domain permission, canonical object identity and retained country/date. Historical-object vocabulary routes this source; no museum request for Mohamed Salah and no fabricated aliases.
- Wired into production recovery after Flickr and before deeper Commons pages, within the existing pool/download/deadline gates. Existing subject matching, image decoding, public eligibility and no-repeated-image rules remain. Source-role warning retains historical origin rather than being overwritten by generic wording.
- Independent review caught cross-provider duplication: a Commons thumbnail and Met original could have different hashes. Added official Met source-link canonicalization and a regression with different bytes. 34 focused source/integration tests pass; PR CI/merge pending at this checkpoint.
- Live adapter test: Coffee pot returned two downloaded/decoded metadata-matching images, met:443173 (Turkey; 2995x4000; SHA256 c332b16765f2b1895f48274a7b714e5169cfb7009f9ad840aba4ded953a48c64) and met:62526 (3000x4000; SHA256 d267d0f4ef907dd3d5317919d0a7030c7b84f67062b135e5525ec12685db921c). These are technical source checks, not final editorial/pixel approval or a complete three-image package. No permanent source-photo files or paid generation.
- Further sources examined: StockSnap explicitly provides CC0 images without attribution (https://stocksnap.io/license); exact Saudi search page was unavailable via web tool, so relevant coverage/automated retrieval remains unverified. Burst terms allow no-credit use under CC0 or its separate license (https://www.shopify.com/stock-photos/legal/terms), but no API/specific topic coverage is established yet. These are candidates, not active integrations.
- Shutterstock requires adjacent credit in editorial contexts (https://www.shutterstock.com/license, credit section); Adobe editorial assets require the supplied credit line (https://stock.adobe.com/license-terms). Do not activate either as a no-credit celebrity solution just because paid access exists. Alamy terms page access was unsuccessful; no rights conclusion.
- Next sourcing gate: test topic-specific StockSnap/Burst imagery and authorized retrieval method, or a supplier agreement explicitly covering no-visible-credit editorial use and automated review. Modern celebrity coverage remains unresolved. No supplier messages, purchases, AI charges or public posts in this step.
