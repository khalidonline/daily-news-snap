# One manual Tawari preparation trial

`publishing-v2-fixed-preview.yml` exposes the existing `fixed-preview` runtime
without modifying the shadow/live workflow. It runs only by manual dispatch on
main, for one lane and an explicit repository-local source-bound selection JSON.
There is no schedule or push trigger. The shared publication concurrency group
serializes it against existing work. Existing package/stage budgets, journal
idempotency, template, text-fit and review checks remain intact.

The job has the existing Anthropic and journal credentials only. It does not
receive publication or messaging credentials and does not run the review sender,
report sender, readiness promotion, delivery request or publisher. GitHub write
permission remains necessary for budget/state journals. `fixed-preview` can
make paid bounded model calls, so dispatch requires authorization for that trial.

The resulting artifact includes runtime output and only the exact new staged
package identified by this attempt's summary. Path validation rejects traversal,
symlinks and historical tracked packages. These are internal drafts, not
owner-approved or display-ready cards.
After a successful run, inspect the original state and exact artifacts, perform
the real mobile/design review, then use the existing upload and uploaded-preview
verification sequence before showing a card. Never fabricate review checks or
regenerate on a delivery failure. Publication needs separate explicit approval.
A failure or held result is a blocker, not a completed trial.

No live trial was run as part of adding this entry point. A current evidence
brief, merged entry point, authorized manual dispatch, and resulting artifacts
are still required. A draft PR does not authorize merging or restarting schedules.

The accompanying 2026-11-04 daily brief selects candidate `720d879aae237bd3`.
It concerns the Sharurah falcon auction and identifies all proposed images as
illustrations internally, not the actual birds/event. The owner requests a strong
relevant falcon image without a visible illustrative-image disclaimer. Do not
claim it depicts the sold bird. Recheck current source-pool membership
and timing at execution; never bypass expiry or substitute a paid selection.
