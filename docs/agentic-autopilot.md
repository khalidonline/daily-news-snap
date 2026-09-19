# Agentic daily and local packages

Run `python -m publishing_v2.autopilot.runtime --mode shadow --lane both` in the
configured main-branch GitHub Actions environment. The workflow runs at 08:00
Riyadh daily. Paid runs are not triggered by code pushes. It requests live mode by default;
the runtime automatically runs both lanes in shadow when the exact engine lacks
recent validation. GitHub Actions schedules can be delayed by runner availability.

The coordinator selects up to four candidates per lane. Separate requests perform
research, writing, visual selection and independent review of sources and actual
rendered cards. The existing templates render one Info plus 2–6 story cards,
with source names on the final story frame only. Packages using CC BY 4.0
images contain at most four editorial frames plus complete end credits, delivered
as one 45–55 second MP4 so images cannot publish without their attribution.
The reviewer sees frames decoded from the final video; its hash is checked before
upload. Public-domain/CC0-only packages can still publish as individual images.
Rejected cards get at most two full rewrite/render/review attempts; then a replacement candidate
is attempted. At most twelve drafts per lane, always within the shared spending
ceiling. Review feedback reaches both writer and visual selector, and image IDs
rejected for relevance are excluded from that candidate's retries. No model has publishing credentials
or an external mutation tool. Sources and model responses are untrusted data.

## Runtime requirements

Existing secrets: `ANTHROPIC_API_KEY`, `BUNDLE_API_KEY`, `BUNDLE_TEAM_ID`,
`TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`. GitHub Actions receives contents-write
authority for its durable journals. The existing `cost-ledger` branch must exist.
`DAILY_BUDGET_GITHUB_TOKEN` is optional when the workflow token can write it.
Every paid call uses `daily_budget.Ledger`, including visual selection and review.
Requests have a bounded 180-second timeout to accommodate image-heavy review.
Failed or ambiguous calls keep their conservative reservations. The daily ledger,
not the per-run report, is authoritative for total spend/reservations.

Specialist roles default to the priced Sonnet model; the production workflow
uses Opus for independent final review. Specialists work at medium effort with an
8,192-token output limit; the final reviewer uses high effort and 16,384 tokens
to leave room for both reasoning and its decision. Research selects
numbered, exact source passages; the program resolves quotations and keeps the
persisted source excerpts below 200 words per source. The independent reviewer
still receives the original retrieved source context. `AUTOPILOT_<ROLE>_MODEL` can select another model
already in `daily_budget.PRICES`. New providers require a reviewed price/usage
adapter. This initial wiring does not make a claim that these models are optimal.

## Rollout

Shadow mode does not publish. A real successful shadow package for **each** lane
records engine fingerprint, review seal, slot, and timestamp. Live mode requires
both records, with the same implementation fingerprint and age under three days.
Manual dispatch with `mode=live` uses this gate. Missing or stale validation
automatically runs both lanes in shadow; it never bypasses the gate. Successful
live runs refresh validation for their lane, so routine operation stays autonomous.
Unattended live scheduling is enabled after real validation of both lanes.
Set repository variable `AUTOPILOT_MODE=shadow` to pause scheduled/deployment
publication; explicit manual dispatch mode takes priority. A failed shadow never
silently enables publishing. Existing manually approved package publishing is preserved.

On activation, an intact, unexpired shadow package from the same Saudi day and
engine can be promoted into an empty live slot. Its existing review and seal are
preserved; rehydrated media is checked again before publishing. Older shadow
packages are not reused as today's content.

On live runs, the approved package and review hashes are saved before calling the
existing Bundle publisher. All public creates use its saved intent and receipts.
Reruns reconcile saved post IDs and never regenerate a publishing slot. Unknown
creates require provider reconciliation; blind retries risk duplicates and are
deliberately prohibited. An expired package cannot start another public create.

## State and visibility

`snapchat-api-state/api-receipts/autopilot-*` contains slot decisions and receipts;
the existing publisher's hash identities deduplicate across manual and agentic
paths. GitHub compare-and-swap saves and a shared workflow concurrency group
serialize operations. Do not delete state to retry a failed slot. Interrupted
generation is held to prevent unbounded spend; publishing recovery retains the
exact approved package. This repo is public: journals contain editorial records,
never API credentials or private audience information.

Actions artifacts contain source metadata, agent receipts, finished cards, review
decisions and per-lane JSON. The operational Telegram report provides status,
attempt cost and the Actions link; shadow output is explicitly identified.

## Initial limits

- Both lanes use dated news feeds with retrieved original articles and encyclopedia
  context. Local topics additionally require Saudi everyday/cultural relevance.
  No timeless local seed fallback remains. Each feed has bounded space so earlier
  sources cannot crowd Saudi feeds out of discovery. It does not yet cover
  every event or a paid research supplier. Unsupported dates/facts are rejected.
  When an underlying event date is unknown, substantive current reporting may
  supply the attention date from verified feed metadata. This is explicitly
  marked `report_date`; cards must not claim the underlying event happened today,
  and the reviewer rejects recycled/evergreen coverage.
- Automated image sourcing accepts Commons public-domain/CC0 metadata without
  stated restrictions, plus CC BY 4.0 assets with complete attribution metadata.
  Required credits are never truncated. Source and license links, creator/title,
  supplied credit notices and crop/resize disclosure travel with the same video.
  No generated documentary imagery or paid Getty dependency is introduced.
- Audience analytics are not connected. Delivery receipts prove provider-reported
  posting, not audience engagement; no learning or growth claims are made.
- The workflow explicitly sets `AUTOPILOT_DAILY_LIMIT_MICRO_USD=10000000`
  for a shared $10/day commissioning ceiling; standalone runtime defaults to $3. Existing charges and outstanding
  reservations survive the CAS-protected upgrade; legacy callers retain their
  own $3 reservation limit. Actual quality and costs are measured in shadow.

Tests: `python -m unittest discover -s tests -p 'test_v2_*.py' -q`.

## Current attention and owner feedback

Both lanes require a retrieved news article from the last 24 hours and supported
timing. The independent reviewer must explicitly pass `current_attention`: the
article must establish a concrete current development and audience reason, not
just have a fresh date. The trigger may remain off the finished cards.
`feedback.py` stores versioned owner rejections shared with editor and reviewer.
Exact rejected triggers are excluded before research, including URL slug/query
variants of the recorded article. Subjects are not permanently banned: a distinct
current development and better narrative may qualify. Feedback changes invalidate
old engine validation. Add future owner rejections there; this is curated feedback,
not an automatic chat ingestion or audience analytics system.

## Bounded editorial recovery

A completed, usage-accounted response with unreadable JSON gets at most one fresh
request, reserved separately against the same daily budget. HTTP errors, refusals,
unknown usage and valid negative review decisions do not trigger this retry.
Format diagnostics are kept in receipts without storing raw model output.
Original articles may follow at most three redirects, validating HTTPS, hosts,
ports and credentials at every hop. Image rights and download rules are unchanged.
Before paid research/drafting, the renderer checks for at least three eligible
subject images and provides their metadata to the writer. This is feasibility,
not image approval: the final selection and pixel review still apply.
