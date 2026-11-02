# Owner-directed reference archive policy

Khalid requested: keep all references independently for later lookup and publish
without reference checks. Applies to manual owner-reviewed information cards.

References remain in each package's sources.json. Historical manifest metadata
is retained, but URL/rights/description fields are no longer delivery gates.
No invented licence or source. Source image byte hashes, output bytes, approval,
expiry, template checks, quota, identity and duplicate protection remain intact.
No autonomous selection/rights route is changed.

Tests reproduced both prior failures before implementation. Targeted tests:
47 passed and 5 subtests passed (owner composite, information request, preview
ready, uploaded preview and delivery). Actual Darb manifest offline validation
passed, preserving identity 925774bce0e16252ccbeb1af9386cc733951f8b57feeb6e389f4ecb637a4bb47.

Full suite attempted in an isolated worktree. Normal collection stopped because
tests/test_publish_cards.py imports unavailable imageio_ffmpeg. Continuing
collection produced 1260 passed, 3 failed, 1 error, 250 subtests passed:
- test_v2_information_request_workflow.py::test_workflow_registration_is_explicit_and_preserves_recovery: assumes no live request file exists, but an authorized request is present.
- test_v2_public_image_credits.py::PublicCreditsTests::test_real_render_to_auto_and_manual_publication: renderer_configuration_mismatch.
- test_v2_route_inventory.py::test_repo_route_inventory_has_no_unreviewed_changes: changed two policy modules, local retry helper and existing us-midterms prepare/render files. Updated inventory hashes ONLY for the two reviewed policy modules; no blanket baseline rewrite.
- tests/test_publish_cards.py collection error: missing imageio_ffmpeg.

These are not an all-suite pass. No old schedules or paid generation were run.
Initial Darb attempt 41409545392 failed before sending at local validation.
Retry 41410373104 uses unchanged media, sources and identity after explicit
renewed owner authorization. Observe its receipts separately for both targets.

Confirmed run41410373104 succeeded: STORY POSTED at08:05:37Z, provider post
957e0a5b-9ab0-4d9b-b35f-b0acc38feb25. SAVED_STORY POSTED at08:06:17Z,
provider post7e91aee8-2cf4-48b0-85ee-78099cfa189a, Snapchat saved story
b0a3f79b-d70b-4346-bf85-a37957257e05. Publisher duration97.811seconds
excludes development, queue and preparation. Both destinations confirmed;
do not retry. Media SHA256 remains7c8566e5721592c3bd37c5be78e15589e40cabecd708a7aa6fff1126510383c3.
