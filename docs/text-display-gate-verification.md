# Text-only display gate verification (4 November 2026)

Base commit: `4718445e05594a2cd851cb2280234422af637a67`.

## What changed

The fitter already existed. The November 4 incident was an agent skipping it,
not incorrect template metrics. The only application consumers found were the
fitter CLI, renderer wrapping helper, and the approved November 4 render script.
There is no repository-owned send hook for arbitrary assistant chat.

The new `--display` mode is a safe handoff for agents and future writers: it
remeasures first, emits only passing text and the exact master CTA on stdout,
and keeps its JSON measurement/receipt on stderr. Its old JSON mode is retained.
Root authoring instructions now require this mode. Code cannot force a caller
who bypasses the command to follow those instructions.

## Reproducible before/after

This uses the existing historical Ryanair regression fixture, not a new news
selection or approval. No wording is automatically shortened or changed.

- Overflow input: replace the fixture bullets with the original 108-character
  paragraph from `test_original_three_line_paragraph_rejected`.
- Existing JSON mode: rejects it, but stdout contains diagnostic JSON including
  the rejected candidate. This was an internal diagnostic interface, not a safe
  stream to forward as a text card.
- New display mode, same input: exit 1; stdout is empty; private diagnostics show
  three rendered lines against the two-line limit.
- Passing input: `tests/fixtures/ryanair-text-fit.json`, unchanged. Exit 0;
  headline 35 characters / one line; bullets 75, 68, 76, 78 characters / two lines
  each; closing 39 characters / one line. Counts include spaces and punctuation.
- Output includes exact master CTA: شاركها مع صديقك اللي تعجبه هذي المعلومة.

Run from repository root:

```sh
python -m publishing_v2.information_text_fit --display tests/fixtures/ryanair-text-fit.json
python -m pytest tests/test_information_text_fit.py tests/test_v2_information_text_display.py tests/test_fixed_information_template.py -q
```

Focused verification: 37 passed, one existing Pillow deprecation warning.
The eight new display tests are named `test_v2_*` so the existing offline CI
suite selects them without any workflow or schedule change.
Independent review found no blocking defect. The reviewed inventory delta
changes only the fitter implementation hash; unrelated inventory debt is not
silently approved by this change. The owner explicitly authorized uploading
this implementation, tests, documentation and single inventory update to a
review branch and draft PR. No merge or deployment is authorized.

No template, renderer, fonts, approved content, publication requests, delivery
workflows, schedules, or external posting calls changed. Text fit is not factual
review, visual design approval, or permission to publish.

## Full-suite comparison

Final exact code and tests: `python -m pytest -q`: **3 failed, 1299 passed,
250 subtests passed**, 2 deprecation warnings, 311.61 seconds. No new failed test
names compared with the pre-implementation run (1291 existing passes plus the
five intentionally failing initial display regressions). Eight new tests pass.

Inherited failures, left unchanged:
- `tests/test_v2_information_request_workflow.py::test_workflow_registration_is_explicit_and_preserves_recovery`: historical publish-request file exists, test expects none.
- `tests/test_v2_public_image_credits.py::PublicCreditsTests::test_real_render_to_auto_and_manual_publication`: legacy renderer configuration mismatch.
- `tests/test_v2_route_inventory.py::test_repo_route_inventory_has_no_unreviewed_changes`: existing unreviewed us-midterms and us-results prepare/render scripts (four paths).

This is not an all-green repository claim. Full verification includes the locally
reviewed fitter-only inventory hash change, included in the review branch.
