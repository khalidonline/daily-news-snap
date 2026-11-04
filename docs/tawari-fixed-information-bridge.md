# Tawari fixed-information preparation lifecycle

## Scope and current status

A new explicit `runtime --mode fixed-preview` branch now invokes the existing
candidate selection, source, timing and research gates, then a separate fixed
information writer/reviewer contract. It produces one or two cards with 1–4
bullets, required image captions and claim references. Factual truth and
caption/photo matching still require review. It measures exact copy
before requesting independent text review, selects/retrieves eligible photos,
and stages current-template outputs through `information_bridge.stage`.

The terminal state is `awaiting_information_review`, never `shadow_passed`,
`approved`, or `published`. A repeated call returns the same handoff without
another writer/render attempt. It cannot be promoted through the legacy live
mode. No readiness promotion, ready-inventory entry, media notification or
provider send is performed by this branch. Both destination approvals remain
false, and final human/agent visual review plus owner authorization still follow.

The production command is now wired (do not run without independent authority
for paid calls and external state writes):

```sh
python -m publishing_v2.autopilot.runtime --mode fixed-preview --lane daily \
  --selection editorial/selected/current-brief.json --output autopilot-output
```

**No existing workflow/schedule is switched to this mode.** Default shadow/live
legacy behavior and challenge routes are unchanged. This is testable integrated
preparation code, not an activated or unattended publishing system.

The standalone offline adapter remains available for a separately reviewed,
fixed-format package and already cached source bytes:

```sh
python -m publishing_v2.autopilot.information_bridge \
  --package-json out/candidate/package.json \
  --sources-dir out/candidate/current \
  --name tawari-example-20261104
```

Ordinary legacy autopilot packages are **not** compatible with this import:
legacy `validate_draft` requires 3–7 cards and prohibits an info image caption.
The new fixed writer contract resolves this for fresh preparation rather than
silently trimming or rewriting already-approved legacy copy. The standalone
legacy-shaped adapter input must have been separately reviewed for the 1–2-card
contract and exact captions; it is not an automatic legacy migration.

The input is a package object, not the enclosing pipeline state. Cached sources
must be `source-00.jpg`, optionally `source-01.jpg`, with matching selected-image
SHA-256 values. Output names are plain lowercase slugs, never absolute paths.
The adapter preserves exact source bytes and title/bullets/closing text. It does
not westernize digits, shorten text, or fork the current renderer. Legacy body
input is treated as one exact paragraph. The master sharing CTA remains intact.

## Explicit stop conditions

- Only one or two information/story cards. Existing 3+ card autopilot packages
  need a separately reviewed rewrite; this command never drops public content.
- Existing valid `text_approval` and timezone-aware `as_of`/`expires_at` required.
  This machine approval is **not** owner publication approval.
- Video/challenge imports, missing captions, stale source hashes and text that
  does not fit stop. No fallback renderer or generation is attempted.
- Images needing visible attribution stop for explicit fixed-template review.
  Legacy attribution receipts cannot carry over to different output pixels.
  No legally required credits are silently removed or drawn over the master.
- Existing destination package names are never replaced, including drafts.
  Resume/reconcile an existing approved identity through its original route;
  never create another identity to recover a send.

The output contains exact PNGs, copied sources, text-fit receipts, preserved
input/source records, and Story plus Saved Story manifests with **both approvals
false**. The design report contains geometry/hashes but an empty review section.
The profile baseline is intentionally blank. No prepared seal, preview receipt,
owner authorization or publish-request file is manufactured.

## Remaining guarded lifecycle

1. Inspect real exports, source/caption meaning, colors and separate 390px
   Story/Saved Story overlays. Record only real final-hash-bound findings in
   `design-review.json`. Complete the actual profile baseline and timing.
2. Run the existing `prepare-local-preview`. It refuses the untouched bridge
   output because actual review and profile evidence are still missing.
3. Upload the complete draft with both approvals false through an authorized
   workflow, then run the existing `prepare-preview`. Only its freshly verified
   uploaded bytes permit display. A local fixture test is not this production
   verification.
4. Obtain exact owner publication authorization. Use the unchanged
   `information_request authorize` and existing publish-approved-package route.
   A request commit is a live-send action; this bridge never creates it.
5. Existing `deliver_information` validates both destinations, sends Story then
   Saved Story, preserves independent receipts, and handles partial failures
   through the original durable publisher identities. Never regenerate approved
   media or infer success merely from a workflow start.

## Offline verification and what it proves

`tests/test_v2_fixed_preparation_pipeline.py` executes the real runtime main and
Pipeline preparation branch with fake external agents/sources/journals, then
asserts no readiness/legacy-publish promotion.
`tests/test_v2_tawari_information_bridge.py` uses real pinned fonts/template,
local files and a temporary Git repository. Network sockets are denied. It
proves draft guards and fixed rendering, no overwrite, rejection cases, and
compatibility with preparation, immutable-byte comparison, synthetic approval
staging and dual-destination dispatch. Synthetic review/authorization data exist
only in temporary test fixtures and are not review or publication authority.
The final provider subprocess boundary is replaced; no Story or Saved Story is
actually published. The companion delivery suite exercises real publisher
logic with fake transports/journals, including uncertain archive responses and
retry deduplication.

```sh
FONT_FAMILY=Almarai THEME=light python -m pytest -q \
  tests/test_v2_tawari_information_bridge.py tests/test_v2_fixed_preparation_pipeline.py \
  tests/test_fixed_information_writer.py \
  tests/test_v2_prepared_information.py tests/test_v2_uploaded_preview.py \
  tests/test_v2_information_request.py tests/test_v2_deliver_information.py
python -m publishing_v2.route_inventory
```

This does not establish live provider receipts, real profile state, factual
editorial quality, a deployed bridge, or unattended end-to-end automation.
Activation still requires independently authorized production testing and
verified scheduler/provider outcomes. Existing legacy scheduling is not evidence
that this fixed-preparation branch has been deployed.

## Readiness dependency

This change is separate from PR #317 (`fix/tawari-offline-stabilization`), which
binds engine readiness to the current design master, fonts, original logo and
base artwork. Review and integrate that fix independently before considering
any production readiness decision. This branch does not imply #317 is merged,
does not promote a historical shadow, and does not certify autonomous readiness.
