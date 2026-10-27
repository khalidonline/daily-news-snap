# Unified publication preflight implementation plan

> For agentic workers: use superpowers:executing-plans after owner review. No live posting or schedule execution.

**Goal:** Enforce the current ExecutiveSaudi design rules on every new public mutation, not only the manual CLI.

**Architecture:** A shared, final-byte-bound design report is checked before upload/create in supported routes. Reconciliation of existing operation IDs remains read-only and must not create replacement posts. Legacy routes fail closed until migrated; no old schedule is enabled.

**Tech stack:** Python, Pillow, ffprobe/ffmpeg, pytest, GitHub Actions.

**Spec:** publishing_v2/design-settings.json, revision 2026-10-27-master-5; AGENTS.md; publishing_v2/AGENTS.md.

## Verified findings

- bundle_api.main invokes readability checks, but publish itself only invokes the challenge contract for new deliveries.
- autopilot/runtime.py invokes publish with plain media lists; the manual readability entry point is not used there.
- group_recovery.py has its own POST create path.
- saved_story_api.py verifies approval/hash/provider receipts but does not call the current design validator.
- publish_cards.py and safe_publish_cards.py retain older delivery entry points and require explicit audit, not an assumption of inactivity.
- Normal publish and Saved Story reserve only the requested count; master requests two operations retained.

## Global constraints

- 1080x1920, Regular typography, maximum two rendered lines per bullet, current numeric palette, intact CTA and destination-specific safe area.
- Do not infer Saudi phrasing, image provenance or visual meaning from pixel validation: require an honest hash-bound review.
- Preserve approval, rights, duplicate protection, durable intent and receipts.
- Do not reinstate spending-ledger verification; retain USD3 production cap.
- No production, publishing, deleting posts or running legacy schedules during tests.

## Review focus

- Modified/re-encoded bytes after review must fail.
- Missing/stale report or settings revision must fail before any upload/create.
- Existing pending receipts must reconcile without a new create.
- Challenge audio/countdown/reveal must remain required.
- Old already-published archives need current review before a new archive, not automatic recreation.

## Task 1: Common final-byte contract

Files: create publishing_v2/design_contract.py and tests/test_v2_design_contract.py; reuse readability.py, raster_review.py and challenge_contract.py.

- [ ] Write failing tests for wrong dimensions, missing report, changed SHA256, stale settings revision, absent exact ink colors, invalid role boxes and destination mismatch.
- [ ] Implement validate_design(media, report, settings, placement), returning a validated hash-bound result or raising before side effects. Keep actual raster inspection separate from unsupported font identity claims.
- [ ] Test positive information and challenge fixtures, protected photograph regions and antialiased text edges.

## Task 2: Route integration

Files: bundle_api.py, autopilot/runtime.py, group_recovery.py, saved_story_api.py; audit publish_cards.py, safe_publish_cards.py, news_bot.py and workflow entry points.

- [ ] Write tests proving invalid media causes zero upload/create calls for STORY, SPOTLIGHT, grouped delivery, autopilot, recovery and Saved Story.
- [ ] Invoke the shared contract at new-mutation boundaries; preserve live approval checks and immutable receipts. Reject legacy new creates unless they supply the same validated contract.
- [ ] Require live capacity for planned creates plus reserve_operations=2. Reconciliation must not require new-create capacity.
- [ ] Test previously POSTED and ambiguous states never create duplicates.

## Task 3: Coverage and release checks

Files: tests/test_v2_publication_route_coverage.py and .github/workflows/publishing-v2-tests.yml.

- [ ] Inventory all provider mutation call sites and pin an explicit allowed-route list; test newly added unguarded call sites fail CI.
- [ ] Run the full pytest suite offline and document failures, including unrelated ones. Do not use live credentials.
- [ ] Run static mutation-path inventory again; update AGENTS references to current master revision.
- [ ] Submit a code review with exact supported/blocked routes. No claim of universal enforcement until checks pass and the change is deployed.

## Status

Audit and implementation plan only. Runtime code and workflows have not been changed. Owner review is required before implementation under the planning workflow.
