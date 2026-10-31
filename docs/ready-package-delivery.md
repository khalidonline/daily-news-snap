# Ready-package information delivery

## Before preview

Render and inspect the exact approved master once. Stage the final export,
source images, real hash-bound design-review, manifest and archive-approval in
`approved/<package>/` on main before presenting the preview. Keep both approvals
false until explicit publication authorization. Never invent review evidence.

Run from repository root:

```sh
python -m publishing_v2.prepared_information prepare-preview --package example-20261031
```

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

Record approval in manifest and archive-approval without changing the export.
Update archive `manifest_sha256` to the exact authorized manifest bytes. Only
approval booleans, owner-review reference/time, and archive authorization/hash
are excluded from the content seal. Existing owner/design validators still apply.

Dispatch **Publish an owner-approved package**, input `package`, default mode
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
