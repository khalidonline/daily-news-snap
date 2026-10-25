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
