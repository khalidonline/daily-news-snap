## عرض بطاقات PNG داخل المحادثة — اعتماد خالد 11 نوفمبر 2026

عند عرض بطاقة جديدة أو معدلة، اعرض ملف PNG النهائي نفسه كصورة مضمّنة في الرسالة من مساره الفعلي داخل مجلد التصميم، مثل بطاقة العطور. تأكد أن الملف موجود، واستخدم رابط `sandbox:` بمساره المطلق. ضع تحت الصورة رابط «افتح التصميم بالحجم الكامل» لنفس الملف.

## Daily spending ceiling — owner decision 4 November 2026

The owner explicitly removed the aggregate $3/day ceiling after being warned
that spending could exceed it without a daily cap. Current production accounting
and autopilot factories use no aggregate daily ceiling. This supersedes older
USD3 spending-ceiling text, including historical design-master wording. Preserve
package/stage limits, known-provider and finite-request controls, ledger integrity,
held routes, publication approval, quotas and schedules. Removing the ceiling
is not permission to generate, publish, deploy or run a held workflow.
The sealed design master and historical approved packages are not rewritten by
this code change. See docs/daily-budget.md for scope and rollout compatibility.

# Mandatory publication preflight

## FIRST: text-card requests — owner correction 4 November 2026

When Khalid asks for a text card (including «عطني البطاقة»), the fit gate
runs BEFORE the first user-facing draft, not after «صمم». This includes
writing blocks and revisions in chat, not only repository-generated cards.
1. Read the current master and compose the candidate privately.
2. Run `python -m publishing_v2.information_text_fit --display draft.json` on
   that exact candidate; capture stdout and stderr separately.
3. On failure, revise unapproved wording privately and re-run. Do not expose
   a failed draft or ask the owner to approve fixing an unseen draft.
4. Require exit 0, then present only stdout (the successful exact display_text). Keep the approved
   sharing CTA. Re-run after every wording change; a previous receipt is not
   evidence for new text.
5. If the gate cannot run, report that blocker; never call the draft measured.
For already approved wording that fails, get specific shortening/split consent.
This is an agent execution requirement, not a claim that repository code
can intercept arbitrary chat. Do not add a second renderer or change fonts.
Incident evidence: the unmeasured election draft had a two-line headline and
four three-line bullets; the shortened candidate passed the existing gate.
The root failure was skipping the pre-review tool, not faulty template metrics.

## Reference archive — owner decision 2 November 2026

For owner-reviewed information cards, keep factual/image references, credits,
rights notes and attachment provenance in approved/<package>/sources.json for
later lookup. Missing URLs or reference metadata must not block delivery.
Do not invent references or rights. Existing historical metadata stays intact.
This supersedes older source-metadata prerequisite wording below and in delivery
docs. Keep final owner approval, selected-source and media hashes, preparation,
design, safe paths, account/quota and duplicate-prevention checks unchanged.

## Browser-free explicit information approval — 1 November 2026

After uploaded-preview verification and exact owner publication approval, use
`publishing_v2.information_request authorize` to stage a hash-bound request.
Upload its three staged files plus preview-receipt.json in one expected-SHA
commit. Updating .github/information-publish-request.json IS the live-send action.
Never create it during development, for old posts, or on design approval alone.
Use current docs/ready-package-delivery.md. Existing checks, journals, original
identity, separate receipts and manual recovery remain. No browser dispatch is
needed for this path; no paid regeneration. Source decisions must be complete
before preview; missing evidence means stop, not edit/reseal content on approval.

## Uploaded preview gate — owner required 1 November 2026

Do not display or link a new information-card preview from a local-only file.
First run `prepare-local-preview`, upload the entire draft package to main with
both approvals false, then run `prepare-preview`. Only the latter's
`UPLOADED_PREVIEW_READY_NOT_AUTHORIZED` result permits showing its preview_paths.
It fetches actual main bytes and compares all media/sources, manifests, review,
settings and preparation. Network failure, missing files or different bytes STOP
preview display. A successful upload tool response is not integrity evidence.
Never substitute `prepare` or a manual boolean for this gate. Preserve the
verified commit and output in the work record. After owner approval change only
authorization metadata, not media. Rights/provenance must already be complete
before preview; don't postpone source metadata work until publication.
This is the mandatory agent/CLI entry point; it cannot intercept arbitrary chat
attachments. No paid regeneration, live publication or schedule changes here.

## Fixed information delivery — owner approved 31 October 2026

Before showing a new information-card preview, stage its exact export, sources,
design-review and draft manifest/archive approval under approved/<package>.
Keep both approvals false until the owner's publication authorization. Run
`python -m publishing_v2.prepared_information prepare-preview --package <package>`.
This seals integrity only, not visual or owner approval. Complete actual review.
Before this command, finish the real mobile overlay reviews for BOTH Story and
Saved Story, palette samples, draft archive fields/profile baseline, and exact
media/source review hashes. Never mark a review passed without inspecting it.
These are pre-preview tasks, not work deferred until the owner says «انشر».
After «انشر», record explicit authorization without changing export/content,
then use the existing publish-approved-package workflow with that package input.
No new per-card workflows; no paid regeneration on delivery failure. Preserve
the same identity and receipts for recovery. See docs/ready-package-delivery.md.

## Text drafts must fit before owner review

Mandatory entry point for morning/evening/Saudi/story information copy:
run `python -m publishing_v2.information_text_fit --display draft.json` BEFORE showing
the textual card. Revise unapproved copy privately until exit 0 / fit:true;
show its exact display_text. Re-run after every wording edit. Character counts
are diagnostics, not a universal maximum: actual pinned-font wrapping and ink
geometry decide. Never shrink or automatically slice words to pass. See
docs/information-text-drafts.md. This is not publication/design approval and
cannot intercept arbitrary chat responses. Challenge paths remain unchanged.

For information cards, measure drafts using the current shared template before
showing the text for approval. Keep each bullet to two rendered lines, with the
approved font and spacing; never shrink the font to fit. Word count alone is
not evidence of fit. Preserve approved wording and the exact final export for
delivery. A delivery failure must not trigger redesign or paid regeneration.
Draft the textual card to the usable width/height of that template from the
start: aim for balanced two-line points, without filler or oversized unused
paragraph space. Preserve the master geometry and equal paragraph gaps; do not
change font size, line spacing, or the template to compensate for an unmeasured
draft. Flag required wording changes before asking for text approval.

For all ExecutiveSaudi publication or design-revision tasks, read
`publishing_v2/AGENTS.md` before making a delivery manifest or workflow.

Classify every new package explicitly. Challenges must retain audio, a working
countdown, and the approved answer reveal. A revised still is a layout preview,
NOT the final challenge. Preserve all unrequested features of the latest
approved version. The sharing CTA is required under the latest owner decision.

Use the current shared publisher and its challenge contract. Never pin an old
publisher, remove the ApprovedMedia wrapper, mislabel the package, fabricate
review evidence, or use a direct API create to evade preflight. A failed check
means fix the requested asset or report the exact blocker, not send a fallback.

Tests and governance changes do not authorize live posting, paid generation,
deletion of existing stories, or starting old schedules.

## Persistent design and delivery master — 26 October 2026

Before drafting, designing, revising or publishing ExecutiveSaudi content, read
`publishing_v2/design-settings.json` in full. It mirrors Library file
`libfile_6959d690ab2c819192706f6f9bbcaffe`; use the revision in the current JSON.
Latest explicit owner corrections supersede older guidance. Keep the two copies
synchronized; never establish competing masters or rely on conversation memory.

For every information/story/news preview and publication, start with
`publishing_v2.fixed_information_template.render` and the current
`information_template` / `numeric_grid_px` in that same master. Do not fork a
one-off renderer or inherit Rice/Kandasa layout defaults. Body is pinned Almarai
44 Bold, right-aligned, two lines maximum. The approved 31-Oct information layout
uses 24px visible ink gaps and equal N+1 paragraph gaps; consume
information_template.approved_layout_override. Challenges unchanged. Other information
text roles are pinned Almarai Regular. Title is one right-aligned line; closing
is one centered line. Caption/image mapping and final mobile review remain
mandatory. The shared delivery gate rejects out-of-region information text and
actual block gaps below 20px. This is not proof of factual or visual semantics.
Challenge geometry, audio and timing are unchanged. Exact emoji assets remain
unresolved; never fabricate their identity. Emoji must be a separate
pinned asset, not redrawn by an image generator. Preserve approved challenge
sound/countdown/reveal and sharing CTA. Record final-hash-bound checks, actual
quota evidence and separate receipts for every approved destination. The owner
removed cost-ledger verification as a posting prerequisite on 27 October;
the production spending cap is not removed.
Do not re-ask settled style choices or repeat a valid publication authorization.
No live posting, deletion, generation or old schedule runs are authorized by
this settings update alone. Existing publisher guards remain unchanged.

## Original brand logo — owner approved 28 October 2026

Use the same original high-quality ExecutiveSaudi logo asset used by news/طواري
cards for future challenges: upper left throughout, and in the countdown area
for seconds 0–3 before digits replace it. Follow `brand_logo` in the current
master. Never crop the logo from compressed video, screenshots or encoded
exports; never redraw it. Resolve and record the original news-template asset
path and SHA before rendering; do not invent an asset identity. Preserve its
proportions/colors and inspect sharpness in final decoded frames at 390px.
Keep the Oxford wordmark/line and all approved challenge audio, countdown,
answer and CTA settings. This instruction does not republish existing posts.

## Saudi salfa voice — owner approved 2 November 2026

Khalid approved the edited ADNOC text (writing block 90642) as the ongoing
voice reference for all future information/news/story drafts. This clarifies
the editorial_master language rule; it does not change design or delivery.
- Write as someone telling a clear Saudi majlis salfa, not reading news.
- Prefer everyday expressions such as تكلمت عن مشكلة، مو بس، الحين، طيب، عشان.
  Avoid newsroom phrasing like حذرت، إيصاله، and repeated بحسب فلان in the card.
- Introduce unfamiliar companies briefly on first mention (أدنوك، شركة بترول
  أبوظبي الوطنية). Explain the actor before using an ambiguous plural verb;
  never imply the speaker is the party drawing inventories without evidence.
- Each point advances cause, change or consequence. Keep numbers and their
  meaning accurate; store references internally. Preserve attribution or
  uncertainty whenever removing it would misrepresent a claim as proven fact.
- Approved closing reference: يعني السالفة مو وين تلقى نفط… بكم يوصلك؟
  Keep the owner's actual edited wording, not a superseded assistant draft.
- Measure every draft in the pinned template BEFORE presenting it. Two lines
  per bullet; if an already approved text exceeds this, request a specific
  shortening approval or agree a two-card split. Never silently shrink fonts.
