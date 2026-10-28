# ExecutiveSaudi delivery rules — owner approved 25 October 2026

Before ANY new publication, classify the package explicitly. For a challenge,
set `content_type: challenge`; never relabel it as information to pass a gate.
The final deliverable is a video, not the still used to review its layout.

Mandatory challenge checklist:
- Final 1080×1920 MP4 with audible approved audio.
- Visible working countdown and the approved answer reveal.
- Fixed approved palette, readable Saudi Arabic, no diacritics.
- Correct safe area tested against mobile UI; no oversized blank footer.
- Sharing CTA retained (latest owner instruction overrides the old no-CTA rule).
- Review the FINAL video, including listening to it and watching the timer and
  reveal, then bind that review to its SHA-256. Never invent passed checks.

Layout-only corrections must preserve the last approved audio, countdown,
answer and delivery properties. Record `challenge_contract.previous` with the
previous repository-local manifest path and SHA-256; preserve `presentation`.
If a requested change alters those properties, obtain a distinct explicit
approval; do not omit the predecessor to escape the preservation check.

All Story delivery uses `bundle_api.publish` / `publish_group`, with the
ApprovedMedia wrapper intact. Temporary delivery workflows must run these
checks too. Do not call `client.create` directly or pin older code to bypass a
gate. Never replace a failed video with a static image or silent slideshow.

`challenge_contract.py` validates the uploaded bytes, stream dimensions,
audio presence/level, timing, and hash-bound checklist. Visual semantics
(timer numerals, correct answer, palette, typography, CTA) still require a
real final-video review; metadata is not automatic visual proof.

Existing manual-video/editorial, budget, live quota, approval, rights,
idempotency and reconciliation gates remain in force. Adding this contract
does not enable an otherwise unsupported video publishing route. No live
posting, paid production, or schedule execution is part of a code-only change.

Previously POSTED items are not recreated. Pending operation IDs are reconciled
without new creates. Do not delete old posts without explicit authority.

## Persistent design and delivery master — 26 October 2026

Before drafting, designing, revising or publishing ExecutiveSaudi content, read
`publishing_v2/design-settings.json` in full. It mirrors Library file
`libfile_6959d690ab2c819192706f6f9bbcaffe`; use the revision in the current JSON.
Latest explicit owner corrections supersede older guidance. Keep the two copies
synchronized; never establish competing masters or rely on conversation memory.

Use its fixed canvas, numeric palette, layout bounds, Regular weight and size
targets, two-line bullet limit, CTA and publishing checklist. Unknown original
font and exact emoji assets remain explicitly unresolved: never fabricate their
identity or declare all fields automatically enforced. Emoji must be a separate
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
