# Balanced information layout — 31 October 2026

Local implementation and preview only. Not deployed to main; no publication.

- New focused suite: 3 passed, including actual glyph-ink bounds, equal paragraph gaps, rejection of changed spacing and overflow.
- Halloween title preserved in full; export 1080x1920; four two-line bullets; line gaps 24px; five outer/inter-paragraph gaps 64,64,65,64,64px.
- Actual mobile export inspected. Header fits the newly approved 95x95 box, making its lettering visibly small; owner should inspect this full-artwork preview before delivery.
- Shared information renderer and geometry/pixel gate migrated locally; challenge-specific geometry code unchanged.
- Full suite attempted: 96 passed, stopped at 10 failures. Not a green full-suite claim. Failures were not repaired as part of this layout task.

Failures reported by pytest:

1. approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_all_five_current_approvals
2. approved/saved-stories/daily-20261007/test_batch.py::ArchiveBatchTests::test_final_nvidia_order_and_media
3. tests/test_auto_image_selector.py::RelevanceFirstWrapperTests::test_named_organization_recovers_with_exact_current_logo
4. tests/test_auto_image_selector.py::RelevanceFirstWrapperTests::test_repository_recovery_asset_is_decoded_with_credit
5. tests/test_breaking_manual_reproduction.py::ManualBreakingReproductionTests::test_breaking_workflow_is_review_only
6. tests/test_breaking_manual_reproduction.py::ManualBreakingReproductionTests::test_workflow_defaults_manual_runs_to_visual_repair
7. tests/test_breaking_visual_relevance.py::BreakingVisualRelevanceTests::test_breaking_no_photo_aborts_with_dedicated_exit_code
8. tests/test_breaking_visual_relevance.py::BreakingVisualRelevanceTests::test_breaking_visual_requires_explicit_yes [neutral subtest]
9. tests/test_breaking_visual_relevance.py::BreakingVisualRelevanceTests::test_breaking_visual_requires_explicit_yes [no subtest]
10. tests/test_breaking_visual_relevance.py::BreakingVisualRelevanceTests::test_breaking_visual_requires_explicit_yes

The first suite collection attempt also required installing missing imageio_ffmpeg; after installation collection proceeded. No production dependencies or schedules were changed.
