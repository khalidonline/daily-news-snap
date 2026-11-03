# Information text before review

Prepare JSON with `headline`, `bullets` (one to four strings), `closing`.
Run `python -m publishing_v2.information_text_fit draft.json` from repository root.
Alternatively pipe JSON on stdin. Nonzero exit means revise privately, preserving
facts, causal links and Saudi phrasing, then measure again. Do not show an
overflowing draft as template-ready. No paid model call or substring truncation
is performed by this command. Approved copy needs specific owner consent to edit.

Success includes exact `display_text`, raw Unicode character counts including
spaces/punctuation, normalized wrapping, line counts, remaining line/width
capacity, actual ink boxes and a receipt bound to wording, settings, font and
implementation hashes. These are Unicode code-point counts, not bytes or a
universal maximum. Two equal-length strings can occupy different widths.

The renderer and text gate share wrapping. Full ink placement is checked by
the existing renderer on disposable in-memory pixels, never saved or shown as
a design. Text fit does not verify claims, image semantics, captions or final
mobile overlays, and does not authorize design/publication. Final design must
still pass all existing uploaded-preview and delivery checks.

Use this entry point for all chat-authored morning/evening/Saudi/story drafts.
Repository code cannot intercept prose typed directly into chat. Retired
autopilot's multi-card `body` schema and its 130/320-character limits are not
this template; no legacy scheduler or writer was activated. Future information
writers must call this gate before exposing a reviewable draft. Challenges are
excluded and retain their existing audio/countdown and layout requirements.
