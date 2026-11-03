# Execution ledger — text-card-pre-display-fit

Base: 91bc2155a97500cf919715ba12cd3224f872fc28. Isolated text-fit worktree.
User approved independent test environment after system installation denied.
No publication requests, approved assets, settings, schedules or paid calls changed.

Preflight: Task 2 consumes Task 1 CLI; JSON fields headline/bullets/closing match.
Ruling: Reuse renderer for ink placement rather than duplicate vertical layout;
shared pure wrapping is extracted. Cost: small in-memory raster overhead per draft.
Ruling: Skill helper scripts are not installed locally; record equivalent execution
ledger in this tracked file for durable progress. Cost: bookkeeping is manual.

RED: 14 new tests failed with missing information_text_fit module.
GREEN: 25 focused tests passed, including 11 existing renderer tests.
Baseline first collection blocked: tests/test_publish_cards.py missing imageio_ffmpeg.
Independent test environment being completed; full baseline and post-change run pending.
No main update yet; implementation remains under verification.

## Final checkpoint 2026-11-03

- Latest focused run: 29 passed (18 new copy-gate tests +11 renderer tests).
- Full baseline at4b15a1b: 3 failed,1273 passed,250 subtests passed.
  The only difference to91bc215 is the plan document (no executable changes).
- First post-change full suite: 3 failed,1287 passed,250 subtests passed.
  Four additional coverage cases and vertical-budget test assertion subsequently
  pass in latest focused run. No claim that this is a final fully green suite.
- Existing failure names:
  - tests/test_v2_information_request_workflow.py::test_workflow_registration_is_explicit_and_preserves_recovery
    asserts no information request exists; an actual historical request is tracked.
  - tests/test_v2_public_image_credits.py::PublicCreditsTests::test_real_render_to_auto_and_manual_publication
    renderer_configuration_mismatch from legacy renderer configuration in full suite.
  - tests/test_v2_route_inventory.py::test_repo_route_inventory_has_no_unreviewed_changes
    baseline missing approved/us-midterms-20261101/{prepare,render}.py changes.
    New module/renderer hashes reviewed and updated only; historical entries untouched.
- Latest focused + inventory run:30 passed,1 failed (the historical inventory paths).
- Whole raster and metadata compared to git-show original renderer on4 two-line
  bullets and2 photos: identical. No font/geometry/settings change.
- Fresh independent review: no blocking code defect. Actual temporary-font/settings
  mutation coverage added. Vertical budget missing: test observed RED(KeyError),
  implementation added, GREEN. Mixed near-boundary line-string coverage remains minor.
- Final: minor (deferred): mixed-script test compares actual geometry, but lacks
  explicit near-boundary expected line strings. Cost: weaker wrapping regression coverage.
- Review exclusions ruled: factual copy review, photo/mobile approval and delivery
  remain outside this code change; no success implied. Historical unrelated files
  and generated test outputs are not included in this change.
- Push review: main publishing-v2 path runs offline checks; live send requires
  distinct trigger/request files, none changed. Keep feature branch while suite red.
- Ruling: preserve work on a separate branch, do not merge to main with inherited
  failures unresolved. Cost: mandatory workflow is not deployed yet.
- Ryanair fixture fit:true: headline35 chars/1line, bullets75/68/76/78chars,
  each2lines, closing39chars/1line. Counts include spaces and punctuation.
