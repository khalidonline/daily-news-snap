# SDD ledger — plan: docs/superpowers/plans/2026-10-27-unified-publication-preflight.md

## Rulings

- Use the existing task-specific scratch clone on branch fix/unified-publication-preflight; no edits to shared main during implementation.
- Enforce at the actual Bundle transport and upload boundary, not only individual callers. Unmigrated morning/evening/autopilot routes fail closed if their final package lacks the current report. No invented approvals or automatic report checkmarks.
- Existing POSTED/pending receipts may reconcile without a new design report; new archive/recovery creates need fresh evidence. Expired archive source approval currently requires renewal; it is not silently extended.
- Legacy news_bot providers are explicitly blocked for new posts. Research and drafting are unaffected. Do not reactivate legacy schedules.
- Future-route CI is a review-required inventory of executable files/workflows, not a security sandbox. A maintainer can deliberately update code and its baseline; branch-protection configuration is outside this change.
- Root full-suite baseline after installing missing test dependencies: 90 failures, 1081 passes, 21 collection/setup errors. Compare names before attributing regressions. No live posting performed.

## Evidence

- Tests first: direct unreviewed create and upload unexpectedly succeeded; absent validator tests failed. After shared gate implementation, all four passed.
- Additional tests first: post update endpoints and legacy helper bypasses failed. After hardening, they passed.
- Real-byte synthetic fixture validates approved upload and post, then rejects modified review; archive requires destination-specific review; pending receipts reconcile without create.
- Palette checks inspect actual saved ink bands and two-line limits; semantic/photo/font identity remains an explicit final-hash-bound review, never inferred from pixels.

## Review and verification

- Independent branch review completed. Closed raw upload, arbitrary upload reuse,
  dominant wrong-color ink, mislabeled challenge, empty destination, stale CI
  settings, missing per-destination overlay and expired pending Story gaps.
- Video design now checks reviewed decoded frames as well as the existing
  stream/audio/timing contract. Real production video still requires its own
  genuine final-frame and listening review; synthetic tests are not that proof.
- Focused integration run: 73 passed plus 7 subtests. Inventory covers 196
  executable/workflow files. No provider writes or old schedules were run.
- Full-suite comparison initially showed the baseline 90 failures / 21 errors,
  two cache/artifact-sensitive old tests, and one new test importing a fake
  news_bot left by another test. The new test now loads the actual module in
  isolation. CI-only environment is explicitly isolated in offline tests.

## Remaining

- Final full run: 1107 passed, 92 failed, 21 errors, 229 subtests passed.
  Compared with the clean baseline, the only extra failures are the existing
  CENTCOM sidecar/cache test and strict-vision metering cache test. All new gate
  tests pass, including a separate GITHUB_ACTIONS=true offline run: 28 passed.
- Full project suite is not green; do not merge or describe deployment as done.
- Runtime is not deployed to main. No promise of universal live enforcement before merge.
- Branch protection and externally pinned callers cannot be enforced by this
  local patch. Future route inventory changes require a human review, not a
  blind hash refresh. Research schedules remain untouched.
