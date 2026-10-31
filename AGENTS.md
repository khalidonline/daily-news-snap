# Mandatory publication preflight

## Fixed information delivery — owner approved 31 October 2026

Before showing a new information-card preview, stage its exact export, sources,
design-review and draft manifest/archive approval under approved/<package>.
Keep both approvals false until the owner's publication authorization. Run
`python -m publishing_v2.prepared_information prepare --package <package>`.
This seals integrity only, not visual or owner approval. Complete actual review.
After «انشر», record explicit authorization without changing export/content,
then use the existing publish-approved-package workflow with that package input.
No new per-card workflows; no paid regeneration on delivery failure. Preserve
the same identity and receipts for recovery. See docs/ready-package-delivery.md.

## Text drafts must fit before owner review

For information cards, measure drafts using the current shared template before
showing the text for approval. Keep each bullet to two rendered lines, with the
approved font and spacing; never shrink the font to fit. Word count alone is
not evidence of fit. Preserve approved wording and the exact final export for
delivery. A delivery failure must not trigger redesign or paid regeneration.

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
