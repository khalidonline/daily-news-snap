# Approval-triggered Information Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Remove browser dispatch from explicit owner-approved information delivery.

**Architecture:** An offline helper stages exact authorization metadata and a hash-bound request. A narrow push trigger in the existing workflow validates the request at its event commit and invokes the existing guarded publisher. No new provider client or rendering path.

**Tech Stack:** Python, pytest, JSON, GitHub Actions and existing GitHub connector.

**Spec:** docs/superpowers/specs/2026-11-01-approval-trigger-design.md

## Global Constraints
- No live publication, old-post replay, paid generation or schedule changes during development.
- Preserve content, template, sources, journals, user changes and current account/quota/approval/idempotency checks.
- Information only, Story plus Saved Story, ONE_WEEK; existing global concurrency group with cancel-in-progress false.
- Install no request file; workflow deployment must not trigger a post. Future request only after explicit approval of exact preview.
- Fresh main, isolated worktree, expected-SHA update, no force or extracted credentials.

## Review Focus
- Multi-commit pushes must not silently ignore a request change; event before/head range checked explicitly.
- Request swapping or unsafe paths/symlinks must fail before publisher invocation.
- New media or changed settings must invalidate old preview and approval.
- Duplicate/retried requests and ambiguous provider results retain original identity and receipts.
- Missing rights/provenance cannot be hidden by resealing content at approval time.

### Task 1: Offline approval and request contract
**Files:** Modify publishing_v2/prepared_information.py; create publishing_v2/information_request.py and tests/test_v2_information_request.py; extend tests/test_v2_uploaded_preview.py if present, otherwise locate existing uploaded-preview tests before edits.
**Interfaces:** prepare-preview additionally persists preview-receipt.json containing verified commit and exact compared-path hashes after successful comparison; authorize_request(package_dir, owner_reference, now) stages approvals and request only after checking receipt/current bytes; validate_request(root, request, now) returns the one package path or raises ValueError. Request version 1, exact manifest/archive/prepared hashes and existing identity.
- [ ] Write failing tests: valid synthetic preview produces one hash-bound request with unchanged assets; draft, expiry, empty owner reference, altered settings/media/source, traversal, symlink and missing receipt produce no authorization/request writes.
- [ ] Run pytest tests/test_v2_information_request.py -q; confirm failures are missing feature, not fixture/network errors.
- [ ] Implement pure prevalidation and transactional file staging; preserve originals on failure. Separate source licensing provenance from newly recorded exact-export owner editorial acceptance; never silently rewrite source facts or weaken the seal.
- [ ] Run new tests plus existing prepared/uploaded-preview tests; all targeted tests must pass. Commit only scoped files.

### Task 2: Existing workflow integration and safe rollout
**Files:** Modify .github/workflows/publish-approved-package.yml, publishing_v2/information_request.py, publishing_v2/route-inventory.json, AGENTS.md, publishing_v2/AGENTS.md, docs/ready-package-delivery.md; create tests/test_v2_information_request_workflow.py.
**Interfaces:** information_request CLI resolves event request only for main push changing .github/information-publish-request.json in before..head; validates using Task 1 contract and prints sanitized package output. Manual dispatch remains supported. Existing deliver_information unchanged unless tests demonstrate a necessary narrow integration fix.
- [ ] Write failing workflow tests asserting narrow push path, exact event checkout, no wildcard package scan, original concurrency and publisher, no direct provider API, no installation request, ordinary push no send, malformed request zero send.
- [ ] Add synthetic multi-commit/event tests and actual publisher-with-fake-client retry tests: already POSTED is not recreated; ambiguous archive stops until reconciliation, Story receipt retained.
- [ ] Run failing tests, implement minimal workflow/CLI integration, then run tests/test_v2_information_request.py tests/test_v2_information_request_workflow.py tests/test_v2_prepared_information.py tests/test_v2_deliver_information.py and uploaded-preview tests.
- [ ] Record fresh baseline and full suite in isolated disposable copy (tests may write state); identify existing failures separately and add no new failures. Review updated entrypoints before updating only their inventory hashes; never suppress protections.
- [ ] Review diff including push side effects; ensure no request file or package approvals included. Update these checkboxes and record test results. Push tested scoped changes using current expected main SHA; preserve concurrent changes. No live test post.

## Self-review and handoff
Spec constraints mapped to both tasks; five Review Focus cases explicitly tested. Execute natively (recommended for this small coupled change) after owner plan confirmation. No implemented speedup claimed; future independently approved publication supplies live timing.
