# Ready-package information delivery

## Before preview

Render and inspect the exact approved master once. Stage the final export,
source images, real hash-bound design-review, manifest and archive-approval in
`approved/<package>/` on main before presenting the preview. Keep both approvals
false until explicit publication authorization. Never invent review evidence.

Run from repository root before uploading (this does NOT permit display):

```sh
python -m publishing_v2.prepared_information prepare-local-preview --package example-20261031
```

Upload the complete draft package to main, approvals false, and compare returned
Git blob SHAs with local `git hash-object` values. For large binary transfers,
never use a possibly truncated command-output string as the payload; use bounded
chunks and verify the full blob identity. Then run the mandatory display gate:

```sh
python -m publishing_v2.prepared_information prepare-preview --package example-20261031
```

This command freshly fetches main into a temporary bare repository and reads
actual bytes at its immutable commit. It compares every media/source asset,
both manifests, sources.json, design review, settings and prepared content.
Only `UPLOADED_PREVIEW_READY_NOT_AUTHORIZED` plus preview_paths permits display.
Missing, changed, incomplete or inaccessible uploads fail closed. The command
does not authorize or publish anything. Local preparation remains available for
staging, never as a substitute for the display gate. Arbitrary chat attachments
are outside code interception; AGENTS.md requires this entry point for all
information previews. Challenges retain their separate contracts.

`prepared.json` seals content, settings, assets and review; it cannot authorize
publishing and does not prove that text, photos or layout are semantically right.
Prepare expiry dates and destination fields before sealing. A changed export,
source, caption, setting, review or content requires review and preparation again.

The pre-preview command rejects incomplete destination overlay reviews and draft
archive fields, and runs the existing pixel/geometry gate for BOTH destinations.
Prepopulate exact media/source hashes in owner_review, but keep both approvals
false and do not claim the owner has reviewed an unseen export. Inspect and record
the real final 390px overlay review before this step, not after «انشر».
Existing `prepare` remains an integrity utility, not evidence of preview readiness.

Textual cards must already be measured with the shared renderer: one headline
line, up to four balanced two-line bullets and one closing line. Fit the wording
to the master text region without shrinking fonts, changing fixed geometry or
adding filler. Show only copy which fits; obtain approval before shortening
already-approved copy. This update does not redesign or republish existing cards.

## After owner approval

### Browser-free request (information only)

The uploaded preview command now saves `preview-receipt.json` locally only after
comparing the real Git draft. Include this receipt in the authorization commit.
It contains the immutable draft commit and all compared content hashes, and is
not itself owner approval. Missing/old receipts require a newly verified draft;
never manufacture a receipt for a published package or reseal changed content.

After the owner's exact-preview «انشر», run from the repository root:

```sh
python -m publishing_v2.information_request authorize --package example-20261101 --owner-reference 'Exact owner authorization reference' --output /tmp/new-approval-stage
```

Use a fresh output directory. This offline command leaves the draft untouched
and stages ONLY the authorized manifest, archive approval and
`.github/information-publish-request.json`. Upload these three files AND the
verified package's `preview-receipt.json` together to main using expected SHA.
Preserve `prepared.json` and all media bytes. Pre-preview source editorial-use
decisions/provenance must already be complete; the helper refuses to change them.

**That commit is the live-send action.** Do not create/update the request for a
test, design revision, maintenance operation or general workflow approval.
The existing workflow triggers only on this request path, checks exact event
commit bytes and the whole push range, and uses the existing guarded publisher.
No browser dispatch is needed. No request file is installed with the code.

If the expected-SHA update is rejected, re-read main and check for a prior
accepted request/run before retrying. Never blindly submit or choose a different
identity. Record run ID, Story receipt and Saved Story receipt separately.
Manual dispatch remains recovery for the same unchanged approved package.
Do not claim time saved until a future approved live send is measured.

Record approval in manifest and archive-approval without changing the export.
Update archive `manifest_sha256` to the exact authorized manifest bytes. Only
approval booleans, owner-review reference/time, and archive authorization/hash
are excluded from the content seal. Existing owner/design validators still apply.

For explicit manual recovery only, dispatch **Publish an owner-approved package**, input `package`, default mode
`prepared-information`. It validates both authorizations, invokes the existing
Story publisher, then the existing Saved Story publisher. No new workflow,
render, model call, media regeneration or alternate direct API route is needed.
Story duration is ONE_WEEK. Challenges remain on Story/Spotlight, not this route.
`legacy-story` explicitly preserves the older Story-only workflow for existing
packages; it never implies archive approval or bypasses existing guards.

## Failure and recovery

Re-run the same unchanged package while authorization remains valid. Existing
durable publisher journals reconcile pending IDs and prevent duplicate creates.
An ambiguous intent without a confirmed ID stops; do not invent a new identity
or delete its receipt. Expired approvals require renewed authorization and
preparation, not removal of checks. Do not claim completion from workflow start.

Output records Story and archive outcomes separately. A failed subprocess means
UNCONFIRMED_CHECK_RECEIPTS, not proof that nothing was sent. Archive failure
does not erase a completed Story. Successful completion means the guarded
publishers confirmed their own delivery/receipt paths. Existing account, live
quota (two reserved operations), review, expiry and idempotency gates remain.
USD3 daily production cap stays; a cost ledger is not a posting prerequisite.

## Timing evidence

Output separates preflight, Story, archive and total seconds. Preparation is
measured separately. Queue duration is not available inside this CLI; obtain it
from Actions run/job timestamps. Do not report CLI total as approval-to-post time.
The Ramses run took about 2m15s in Actions; the larger
13-minute delay included work before dispatch. This change removes per-card
workflow setup and moves staging before review; it does not promise instant
provider processing. Measure real improvement on the next independently
authorized publication. Development tests must never resend Ramses.
