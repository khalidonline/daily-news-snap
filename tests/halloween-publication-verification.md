# Halloween publication verification — 31 October 2026

Final immutable PNG SHA256: 13a309585bc1ba90c1d1825e2bfcbce637b2eb6fa19398ea461f01645cb53af3.
No regeneration or pixel edits. Final full-resolution and 390px modeled Story-player
overlays inspected; three captions individually match the photos. CTA remains visible.
Native layout evidence recovered from the final renderer output and checked against pixels.

Focused command: `python3 -m pytest -q tests/test_balanced_information.py tests/test_v2_design_contract.py`.
Result: 33 passed. Final package CLI: validated_not_published for STORY and SAVED_STORY.
Pre-migration regression: four of five balanced-template tests failed, including
out-of-region title and unsupported third caption; all five pass after migration.
Main's concurrent challenge filled-option/reveal checks preserved verbatim.

Broad command: `python3 -m pytest -q --maxfail=10` was attempted, not a green suite.
Latest result: 10 failed, 89 passed, stopped at configured failure limit. Failures:

- test_auto_image_selector.py::RelevanceFirstWrapperTests::test_named_organization_recovers_with_exact_current_logo
- test_breaking_manual_reproduction.py::ManualBreakingReproductionTests::test_breaking_workflow_is_review_only
- test_breaking_manual_reproduction.py::ManualBreakingReproductionTests::test_workflow_defaults_manual_runs_to_visual_repair
- test_breaking_map_time_fallback.py::BreakingMapFallbackTests::test_rejected_generic_commons_photo_falls_through_to_exact_centcom_seal
- test_breaking_visual_relevance.py::BreakingVisualRelevanceTests::test_breaking_no_photo_aborts_with_dedicated_exit_code
- test_breaking_visual_relevance.py::BreakingVisualRelevanceTests::test_breaking_visual_requires_explicit_yes (including neutral/no subtests)
- test_breaking_visual_relevance.py::BreakingVisualRelevanceTests::test_centcom_seal_uses_retained_official_source_when_event_says_us_military
- test_breaking_visual_relevance.py::BreakingVisualRelevanceTests::test_curated_commons_centcom_seal_is_registered

Earlier incomplete workspace runs also lacked assets, news_bot.py and pytest;
those were environment failures, not final-export failures. The recovery asset
test passed after its directory was restored. No claim that all repository paths
or the complete project suite passed. Legacy breaking/news workflows not executed.

Route changes explicitly reviewed: information renderer geometry and triptych,
information-only gate geometry, and a manual fixed-Halloween workflow invoking
the current guarded publisher then current Saved Story API. No direct creates,
gate exemptions, paid generation, deletion, or scheduled production.
