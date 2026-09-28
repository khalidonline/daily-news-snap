# Approved copy → deterministic design

Render-only entry point (no writer, researcher, remote image fetch or publisher):

    python -m publishing_v2.approved_copy --copy approved-copy.json --assets photos --output review

Input: version=1, cards=[one info then story cards], approval={reference, copy_sha256}.
Each card has kind, title, body, optional punch/caption, and a local photo path.
After explicit owner copy approval, record its conversation reference and the
`copy_hash(cards)` digest. The digest binds exact visible text, including captions.
It is an integrity check, not an authentication mechanism or publication approval.
Do not set it on drafts awaiting approval.

Photos must already have provenance/rights checked. This command never downloads
or generates them. Existing visual, photo-rights, readiness, expiry, budget,
quota and publication gates still apply after rendering. Review the actual pixels.
Use only the ordered files in render-state.json, not a directory glob (older
rendered files may remain after a card is removed).

Cache identity covers each card, numbering, photo bytes, renderer files, fonts
and badge assets. Changed outputs are rebuilt; unchanged outputs are reused.
Copy.json preserves exact approved wording. Outputs explicitly remain
production_ready=false and publication_approval=false; no manifest is sealed.
After approval of the finished design, use the existing saved-assets publication
route. A delivery retry must never call production or this renderer.

Verification 2026-09-28: six focused offline tests pass. Actual saved Armani
four-card copy rendered with existing template; repeat reused four of four with
zero new renders. Visual contact sheet checked. No paid model or delivery calls.
This adds an explicit CLI handoff; it does not alter scheduled autopilot routing.
