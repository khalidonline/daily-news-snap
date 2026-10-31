# Ready-package Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** One stable information-card delivery operation after explicit approval.

**Architecture:** Keep current guarded Story and Saved Story publishers. Add an
offline preparation record and a narrow orchestrator; extend the existing manual
workflow rather than adding per-package workflows. Preparation cannot authorize
provider mutations.

**Tech Stack:** Python, pytest, GitHub Actions, existing Bundle API integration.

**Spec:** `docs/superpowers/specs/2026-10-31-ready-package-delivery-design.md`

## Global Constraints

- No live publication, paid generation, schedule changes or deletions in tests.
- Preserve ApprovedMedia and all live account/quota/idempotency/expiry gates.
- Information only: public Story ONE_WEEK and separately approved Saved Story.
- Reserve two operations; USD3 cap; no cost-ledger prerequisite.
- Draft approval stays false; final review and owner authorization stay distinct.

## Review Focus

1. Changed bytes or settings invalidate readiness, including after approval.
2. Draft preparation cannot send, even with live credentials present.
3. Missing archive approval is caught before a new Story is sent.
4. Partial delivery resumes without duplicate Story; ambiguous create stops.
5. Challenges and unsafe paths are rejected without changing their existing routes.

### Task 1: Offline readiness and preparation convention

**Files:** create `publishing_v2/prepared_information.py`,
`tests/test_v2_prepared_information.py`; update `AGENTS.md` and
`publishing_v2/AGENTS.md`.

**Interfaces:** `prepare(package_dir: Path) -> dict` writes `prepared.json` with
status PREPARED_NOT_AUTHORIZED, media/source/settings hashes and review hash.
`verify_prepared(package_dir: Path) -> dict` rejects changes and unsafe paths.
Neither function imports a provider client, creates ApprovedMedia, nor sets
approval true. Existing final authorized validators remain authoritative.

- [ ] Write tests asserting preparation retains approved=false, performs zero
  network calls, rejects traversal/symlinks outside repo and challenges, and
  fails verification after media, source, review or settings changes.
- [ ] Run `python -m pytest tests/test_v2_prepared_information.py -q`; confirm RED.
- [ ] Implement hash sealing and explicit non-authorizing preparation; document
  uploading package and source assets before preview, then recording approval
  without rebuilding media. Do not invent review evidence.
- [ ] Run the same tests; confirm GREEN; commit only this task's files.

### Task 2: Stable Story-plus-archive delivery

**Files:** create `publishing_v2/deliver_information.py`,
`tests/test_v2_deliver_information.py`; modify
`.github/workflows/publish-approved-package.yml` and
`publishing_v2/route-inventory.json`.

**Interfaces:** `deliver(package_dir: Path) -> dict` verifies readiness and both
authorizations, then uses current bundle and archive entry points, retaining
their durable journals. Return each destination status separately. Extract
non-mutating archive authorization checks from `validate_archive` into a shared
helper so the orchestrator can preflight without fabricating a POSTED receipt.
Retain `validate_archive`'s source-receipt checks before actual archiving.

- [ ] Write mocked tests asserting invalid/missing approval yields zero creates;
  success calls Story then archive; failed Story never starts archive; an archive
  retry reuses the Story receipt; ambiguous intent creates nothing; changed or
  expired packages fail; no render/model calls exist in the delivery path.
- [ ] Run `python -m pytest tests/test_v2_deliver_information.py -q`; confirm RED.
- [ ] Implement orchestration and separate elapsed-stage timings. Preserve
  existing reconciliation logic and account/capacity checks, rather than adding
  an alternate direct API client. Keep workflow manual, main-only, and serialized.
- [ ] Make existing workflow accept the prepared package, run shared delivery,
  and emit separate Story/archive outcomes. Preserve legacy behavior explicitly
  for existing non-prepared packages; never silently authorize archiving.
- [ ] Review changed executable entry points and refresh their inventory hashes.
- [ ] Run new tests plus design-contract, route-inventory, bundle and Saved Story
  regression tests from a clean checkout; record pre-existing failures separately.
- [ ] Commit, review the scoped diff, and deploy through the configured GitHub
  connector. Do not extract credentials or retry unsupported local git push.

### Task 3: Verify and document operation

**Files:** add `docs/ready-package-delivery.md`.

- [ ] Exercise an offline draft, rejection without approval, authorized mocked
  delivery, and interrupted-archive recovery. Assert no duplicate creates.
- [ ] Document one package input and one run; no per-card workflow or render.
- [ ] Verify deployed file hashes and workflow input availability without dispatch.
- [ ] Report deployed/offline-tested status honestly. Real elapsed-time reduction
  is measured on the next independently authorized publication, not a duplicate
  Ramses test post. No claim that provider latency is eliminated.

## Self-review

All five review-focus cases are assigned above. This change is limited to
information-card preparation/delivery; no challenge rendering or schedules.
Fresh approval of this plan/execution method is required before product edits.
