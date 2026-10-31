# Ready-package delivery — owner-approved design

Khalid approved this design with «اعتمد» after the publication latency review.

## Intent

Prepare the exact information-card export and delivery material before showing
the preview. One later «انشر» authorizes one stable workflow to publish public
Story and archive it to the public profile. Do not rebuild or regenerate media.

## Approaches

Chosen: extend the existing manual `publish-approved-package.yml` workflow.
It reuses configured credentials and the guarded publishers. Avoid per-card
workflow creation and route-inventory changes during routine delivery.
Rejected: an always-running service adds operating cost and maintenance while
the observed bottleneck was preparation, not the provider's publication time.

## Boundaries

Preparation is not publication approval. Drafts remain non-publishable until
explicit owner authorization. Seal actual export/source/settings hashes; edits
invalidate readiness. Never manufacture visual review, licenses or approval.
Preserve ApprovedMedia, account validation, live capacity with reserve 2,
expiry and event timing, predecessor reconciliation, durable identities, and
separate destination receipts. No daily cost-ledger prerequisite; USD3 cap stays.
Do not publish or republish anything while implementing this change.
Challenges remain on their existing Story/Spotlight routes, never Saved Story.

## Delivery

Select an existing prepared package, record authorization, and dispatch the
fixed workflow. Validate the authorized sealed package, publish/reconcile Story,
then save/reconcile the public-profile archive. Missing or invalid archive
authorization must be detected before the first new Story operation.
If Story succeeds and archive fails, report partial success and resume from
receipts; never recreate Story. An ambiguous create stops for reconciliation.
Report POSTED only from confirmed destination receipts.

## Performance acceptance

Routine publication needs no new workflow, no rendering, no paid model call,
and no source-image reupload during archive. Log preparation, queue, validation,
Story and archive durations separately. Ramses reference: 2m15s workflow,
approximately50s Story and56s archive; not a guaranteed future SLA.
