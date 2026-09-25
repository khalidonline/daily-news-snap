# Apple correction and publishing recovery — 2026-09-25

## Verified findings

- The latest Apple run (36147912342) reached account check and media upload, then POST /post returned HTTP 403. Account connection success is not proof of publishing permission.
- Its export identity is 356d2118d7a908137474de401838f67183911696fc31d6cef4723c06bcbc283d. The remote journal still has SENDING with an upload ID and no post ID. It has NOT been reset or marked unpublished.
- Provider dashboard sign-in is required in the current browser. The reason behind HTTP 403 is unresolved; do not infer quota exhaustion or revoked credentials.
- The shared 2026-09-25 cost ledger records $2.750190 against $3; remaining $0.249810. The previous review confused an $8 environment request with the actual ceiling: autopilot_daily_limit clamps it to $3 after Sep 23. Active approved workflow settings now request $3 explicitly. No paid generation was invoked for this correction.

## Changes

- Apple preparation uses four pinned official product images and locally renders the existing Almarai/light template. Broad image fallback and paid checks on every publication retry are removed from this route.
- Corrected source timing: the product became available Sep 22; the 512GB configuration is due in late October. Four-system performance is attributed to Apple's benchmark, not a universal guarantee.
- Before preparation: source and attention date, claim mapping, card density and exact product image bindings are checked. These are mechanical guards around manually verified evidence; they do not replace editorial judgment.
- After preparation: a manual pixel review binds the manifest and source specification. Changing either invalidates review; delivery hashes protect every image.
- `news_bot.sanitize` preserves Arabic-Indic digits, fixing story counters in the shared rendering path without changing product names such as M5.
- API creation errors record only the HTTP code, operation and timestamp. The journal remains uncertain and blocks retries. Replacement exports must pass predecessor reconciliation.
- The Apple workflow now consumes saved, reviewed media. It does not regenerate images or text and has no model API credentials.

## Recovery boundary

Do not trigger publishing until Bundle provides evidence resolving the prior upload/post attempt. Save a reconciliation record with status NOT_CREATED or DELETED, checked_at and an HTTPS evidence_url in the prior journal only after verifying it in the provider. A POSTED predecessor cannot be marked NOT_CREATED. The guard only reads; it never invents a deletion or absence receipt.

The saved corrected manifest expires at 2026-09-27 00:00 +03:00. If recovery finishes later, recheck the current trigger before considering another publication authorization window. Do not extend expiry to avoid this check.

## Validation

- Four corrected 1080×1920 cards rendered locally with official images; pixels inspected and identical between preview and repository export.
- Targeted recovery/preflight tests cover 403 journal preservation, no duplicate create, uncertain predecessor blocking, image identity, stale timing, missing visual review and Arabic digits.
- A run of the locally available tests found an existing failure: `test_daily_budget.WorkflowBudgetTests.test_paid_workflows_cannot_override_guard_python_path`. This test expects a global sitecustomize guard in the defense/horse workflows, which instead call the shared Ledger directly. The current change does not add a second billing wrapper. Full repository suite not available in this local materialization.

Source: https://www.apple.com/newsroom/2026/08/apple-introduces-new-mac-studio-with-m5-max-and-m5-ultra/
Failed run: https://github.com/khalidonline/daily-news-snap/actions/runs/36147912342
