# Efficient publishing implementation plan

Goal: prevent quota-blocked uploads and paid regeneration on delivery retries.
Architecture: shared publisher quota gate, content/context keyed durable image review cache, explicit prepare vs saved publish entry points. Existing uncertain-delivery guards stay unchanged.
Constraints: $3/day shared ledger; no live publication or paid model calls in validation; no old workflow triggers.

- [x] Test then add UTC daily quota gate for all unsent cards before upload; fail closed on missing/malformed quota; existing IDs can be reconciled without new capacity.
- [x] Test then add image review cache keyed by exact bytes, complete context, prompt and model. Persist via separate GitHub journal entries; cache failures stop work.
- [x] Make horse/defense entry points publish saved reviewed files by default; explicit preparation never publishes. Missing sealed media stops rather than regenerates.
- [x] Add package/stage/attempt cost attribution to ledger and receipts.
- [x] Run focused offline regression suite, inspect changed code and save one atomic GitHub commit without publication triggers.

Review focus: UTC boundary, partial delivery, uncertain create, corrupt cache, changed image/context, missing media, reservations still bounded by $3.

Validation: 50 of 51 available local tests pass offline. The unchanged legacy workflow-name assertion in test_daily_budget fails for publishing-v2-autopilot.yml; it expects an older injected guard step. This partial checkout is not the complete repository test suite. No paid models or live publishing were invoked.

Scope: shared API delivery checks the full unsent count immediately before uploads. Explicit horse/defense preparation also checks before model calls. Other research/shadow preparation is not quota-gated: it can prepare content for a later day. Cache does not bypass final editorial review. Savings need measurement on future runs. Quota can change externally after preflight; API rejection and uncertain-delivery guards remain authoritative.
