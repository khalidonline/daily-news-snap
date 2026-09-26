# Single-package trial — 2026-09-26

Run: https://github.com/khalidonline/daily-news-snap/actions/runs/36203188337
Tested production commit: 37ba6609c96cc0fa9a8df0e4512103359cf40a9c

## Observed result
- Bundle quota verified at 2026-09-26T00:00:51.446993Z (03:00:51 Riyadh): used 0, limit 20, remaining 20, UTC date 2026-09-26.
- Saudi budget date 2026-09-26: charged 0 micro USD, remaining 3,000,000 micro USD.
- Readiness false. No override or second package attempted.
- Full checkout: 906 tests ran, result failures=12, errors=77. This supersedes any implication that the previous partial 103-test result proved full-checkout compatibility.
- Production and publication steps SKIPPED due to failed tests. No title selected, no research/writer/design/repair calls, 0 cards posted; all model-stage charges for this trial = $0. Infrastructure/subscription costs are not included.

## Findings requiring bounded follow-up
1. Current-path test fixtures do not consistently include the new text approval digest or ensure_capacity method: test_v2_public_image_credits, test_v2_multisource, test_v2_publication_selection.
2. Visual planning tests still require image qualification before paid research; production was intentionally reordered to owner-required text-first. Align explicit policy and tests without weakening semantic/source/rights checks.
3. Complete-suite legacy tests refer to deleted Breaking/Topic/Story workflows and removed APIs. Separate retired coverage explicitly, not by ignoring current-path failures.
4. Trial environment lacked ffmpeg and imageio_ffmpeg for video/legacy tests. Add required test dependencies before repeating verification.
5. Budget workflow assertion still rejects another native ledger recovery workflow in the full checkout. Audit all credential-bearing entry points; do not blanket-allow them.
6. Full readiness remains false. A successful future single Daily shadow cannot silently authorize Local production or bypass existing readiness requirements.

Temporary workflow removed after completion in commit 70bcf2a1af0d75d01a05df661d43af04cf1af4b2. Old schedules remain unchanged. Tests/preflight are retained in workflow artifact single-package-trial-36203188337. No blind rerun initiated. Attempt to append the same persistent Library review log was blocked by two HTTP 502 materialization responses; this repository record preserves the findings without overwriting a stale log.
