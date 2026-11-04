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

## Selected-source repair and explicit recovery

A source-bound brief may now pin its original URL, title, publication timestamp
and configured publisher feed. Fixed-preview resolves that exact article among
at most 250 feed items, independently of discovery's first-six ranking. It does
not trust the brief as evidence: the publisher must still return matching
metadata within 24 hours. Missing/changed evidence stops the run. All original
eligibility, source, timing, story, image, budget, review and duplicate checks
still execute. This does not broaden the live/shadow route.

The first real run, 41827775151, stopped before model calls because its falcon
article was absent from Actions' newest-six Al Yaum subset. A local feed snapshot
was over ten hours old, explaining the false confidence from local discovery.
Its diagnostic artifact contains no generated cards, and reports zero cost.

Recovery is not automatic. The optional manual `recovery` input selects a
reviewed request under `editorial/recovery/`. It binds the exact prior journal,
original failed fixed-preview run and immutable selection revision, the current
selection and the same candidate/lane. Only adding the original source pin may
change the brief. Only the narrow pre-selection missing-pool hold with no agent
receipts and no later audit events is accepted. Paid, ambiguous, expired,
changed, already recovered or completed states are rejected. The previous full
state and audit are retained in the same journal; compare-and-swap must confirm
before any further generation. The pinned source is revalidated before consuming
the recovery, so an unavailable source leaves the old held state intact.
Repeating a used request fails closed.

`editorial/recovery/tawari-20261104-zero-call.json` describes the exact first
failed attempt. Its presence does not execute or authorize a retry. A separately
authorized manual run supplies it together with the selected evidence brief.
Do not delete the held journal, alter historical receipts, or rerun automatically.

## Lost writer response and saved-research recovery

The authorized recovery run 41832636354 resolved the original source and passed
live evidence/image checks. It paid for researcher and fixed writer responses,
then stopped at `invalid_fixed_information_text` before staging any card. The
settled receipts total USD 0.237805. The old implementation retained receipt
metadata and research but not the writer decision, so the exact rejected field
or character cannot be established. Ordinary Anthropic Messages responses cannot
be retrieved by message ID. Do not claim that diacritics caused this actual failure.

New preparations durably record a writer intent before the call, then preserve the
exact parsed JSON decision before normalization or validation. This is not a copy
of provider transport bytes or hidden reasoning. Hash-bound context and draft
files permit same-context reuse; missing, altered or uncertain output fails closed
instead of issuing another writer call. Field-level diagnostics record path,
index and code point without leaking the full draft into logs.

Only ordinary Arabic vowel/tanween marks U+064B–U+0652 and U+0670 are removed from
unapproved editorial text. Evidence and claim identifiers are untouched. All
other invalid/control characters still fail validation. Original and normalized
JSON plus a repair audit remain unapproved and not display-ready. The unchanged
fixed template, actual text fit and independent review still apply.

The separate `saved_research` request is restricted to the exact audited hold
with one settled researcher receipt and one settled writer receipt. It requires
unchanged selection, immutable failed run/head, original journal hash and expiry,
then revalidates current source, timing, eligibility, evidence and downloaded
images before consuming recovery through compare-and-swap. Saved research is
reused only when the current evidence snapshot matches. The original receipts,
package budget identity and full audit are retained. Request numbering continues
at three; the replacement writer has one transport attempt, without a format
retry. Normal subsequent review and visual stages retain their existing limits.

`editorial/recovery/tawari-20261104-saved-research.json` describes that exact paid
hold. It is not permission to execute. A separate authorized manual dispatch is
required. This route does not erase receipts, automatically rerun, publish, send
messages or relax owner approval. Offline fixture rendering is not the real
falcon card and does not make that trial complete.

## Deterministic pinned preflight and full-source drift review

Run 41837850989 stopped in free revalidation before changing the held journal or
making another model call. Actions successfully downloaded two primary article
photos, causing generic discovery to stop before the brief's three Commons pins.
Local primary downloads failed instead, hiding this environment difference.
Explicit asset-ID plans now resolve bounded Commons page IDs directly and retain
that exact pool through preflight and the visual catalog. Existing rights,
subject, size, download, duplicate and image checks still apply; missing pins stop
the run. Query-only plans retain the ordinary discovery route.

A separate read-only check found identical supporting excerpts, source IDs and
URLs but a changed full publisher-text hash. That is not proof of a cosmetic
change: a surviving quote can coexist with a correction elsewhere on the page.
Saved-research recovery therefore requires explicit request opt-in
`allow_source_text_drift_review`. Only the full-text hash may differ. Every other
snapshot field and ordering remains exact; fresh research/timing validation runs.
Both old and current hashes are retained in the audit and bound into the new
text-review input. The reviewer receives full current sources, must explicitly
resolve possible corrections, retractions or contradictory context, and must
return `source_drift_resolved: true` before rendering. A missing/failed check
stops preparation. Current source hashes are checked before requesting review.
This exception is confined to the explicitly opted-in saved-research recovery;
normal source snapshots, approvals and replay checks are not weakened.

Recovery preflight failures now write a small allowlisted diagnostic artifact
without changing the held journal or granting preview/publication authority.
No dispatch is automatic. The revised request requires separately authorized
merge and one recovery attempt after review and CI.
The diagnostic filename is not proof of zero calls or unchanged state: unexpected
later persistence errors also reach this handler. Always inspect the journal,
settled receipts and execution phase before making a cost or retry decision.

## Explicit new attempt with an unresolved old reservation

Run 41843181897 passed pinned-image/current-source preflight and reused research,
then stopped with a provider RuntimeError before saving a response. Its artifact
contains only the writer-started intent, journal and summary. The ledger retains
USD 0.329825 for attempt 3, in addition to USD 0.237805 previously settled. The
reservation is not evidence of an actual provider charge; the old HTTP code was
not retained. Never clear or settle it from this diagnostic alone.

The owner separately authorized one new writer attempt while retaining this
uncertainty. `tawari-20261104-retained-writer.json` binds the exact failed journal,
failed workflow/head/selection and exact prior reserved ledger entry. Recovery
reads the ledger without changing it and requires exactly the original two
settled package attempts and this one unresolved reservation. Changed settlement,
extra attempts, identity drift or used recovery fail closed. The same package
budget counts the unresolved amount; the new writer continues at attempt 4 with
one transport call and no format retry. Research is not regenerated. Any pending
source-context drift is still measured against the original research snapshot,
not a newer unreviewed fetch, and still requires the independent review check.

Provider HTTP failures now preserve safe status/role/model diagnostics and only
allowlisted error types and validated provider-supplied request IDs. No raw error
body, prompt or credentials are logged. Unknown request IDs are not invented.
The reservation remains intact, and HTTP failures do not trigger format retries.
This new manifest is not an automatic rerun or a reconciliation of attempt 3.

The owner then explicitly approved a USD 1.10 writing allowance for this trial
only, retaining the prior reservation. The default package writing cap stays
USD 0.75. This scoped allowance requires the exact retained entry, request digest,
package, current day and writer attempt 4 at atomic reservation time. Other
packages, roles and attempts cannot use it. The writer keeps its usual 8192-token
ceiling rather than risking a truncated response. Identical payload pricing is
estimated without any reservation/transport before consuming recovery; the live
atomic ledger still enforces the final bound including all prior charges.
