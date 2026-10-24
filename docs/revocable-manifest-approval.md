# Revocable manifest approval

Scope: `load_package` → `publish` / `publish_group`, including owner-design
and correction manifests. This does not add revocation to the separate
autopilot runtime, Spotlight, saved-story API, or a chat command handler.

The manifest is rechecked before uploads and immediately before new creates.
In GitHub Actions the same path is read from the live `main` branch through
the authenticated Contents API, not from the runner's immutable checkout.
Missing, changed, revoked, expired, malformed, or unreadable approval stops
new delivery. Unchanged media and receipts are retained; no generation occurs.

To stop a package, set `approved` to `false` in its manifest on `main` and
confirm that commit succeeded. A chat message alone is not an implemented
revocation signal. Cancel the active publishing run as an additional operator
action when available. Do not dispatch a replacement run to stop an old one.

There is necessarily a race between the final approval GET and the provider
POST. A request already in flight or accepted cannot be recalled by this
guard. Reconcile its saved post ID; deletion is a separate explicit action.
If approval fails after the durable SENDING intent was saved, that intent
remains blocked for operator reconciliation; do not clear it or automatically
retry. Revocation is not permission to bypass deduplication.

Tests use synthetic media, in-memory receipts and a fake provider. They block
real network access. They are not a live Snapchat delivery test.

Run focused verification:

    python -m pytest -q tests/test_revocation_audit_20261024.py tests/test_v2_bundle.py tests/test_v2_bundle_group.py

Initial defect: 10 revocation cases failed, 2 controls passed. After the fix,
the suite additionally covers stale checkouts, remote failures, valid remote
approval, changed/expired approval, between-card stop, and grouped intent stop.
