# Information text before review

Prepare JSON with `headline`, `bullets` (one to four strings), `closing`.
For the user-facing text handoff, run
`python -m publishing_v2.information_text_fit --display draft.json` from repository root.
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

## Fail-closed display handoff

`--display` invokes the existing fitter on the current candidate on every run.
Only a passing result writes its exact checked candidate text followed by the
master `editorial_master.cta_exact` to stdout (plus a final newline). Failure writes **no draft text to stdout** and exits nonzero. The JSON
measurement/receipt goes to stderr for private inspection, on success or failure.
Do not merge stderr into stdout or send the diagnostics to the owner. A receipt
supplied in input never bypasses remeasurement. Missing fonts/settings/artwork or
invalid input block display rather than produce an unmeasured fallback.

For an agent or future writer, capture both streams and check the return code:

```python
result = subprocess.run(
    [sys.executable, "-m", "publishing_v2.information_text_fit", "--display", "draft.json"],
    capture_output=True, text=True,
)
if result.returncode != 0:
    # Inspect result.stderr privately; revise only unapproved wording, then rerun.
    raise RuntimeError("Text draft is not ready for display")
# Hand off result.stdout exactly; do not copy a previous successful response.
```

The display handoff includes the approved fixed sharing CTA from the master;
it does not change the renderer or its CTA artwork. Missing or blank CTA blocks
the handoff. The receipt binds the master settings containing that CTA. Do not add or change candidate wording after the
check. Use the existing command without `--display` when you need the compatible
JSON diagnostic interface, not as the user-facing display stream.

This boundary protects callers that use it. There is no repository-owned chat
send hook: an assistant can still bypass it by composing prose directly. Root
AGENTS.md therefore requires this command before every text draft/revision.
No retired scheduler, renderer, publication trigger or delivery path is enabled.
