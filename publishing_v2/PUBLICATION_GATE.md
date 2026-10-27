# Shared publication gate

Applies to morning topics, evening topics, manual stories, challenges, public
Story, Spotlight, saved public-profile stories and future delivery routes.
Research schedules are unchanged. This change does not authorize live posting.

Read design-settings.json before rendering. Produce a sibling design-review.json
before presenting the preview. Version 1 binds settings revision and SHA-256,
final card hashes, destinations, content_type, pixel boxes and line counts.
Use tests/test_v2_design_contract.py as the executable schema example, never as
evidence for a real package. Each destination needs its own mobile overlay review.
Human checks must be performed, not filled with invented pass flags.

BundleClient.upload and all post writes enforce the shared check. Existing upload
IDs need hash-bound journal receipts and live source-post proof before reuse.
Legacy news_bot delivery is blocked, not silently rerouted. Unmigrated autopilot
packages are blocked until they carry a genuine review of the current settings.
Challenge frames are checked alongside existing audio/timer/reveal contracts.
Unknown font identity remains a manual reference-image comparison, not an OCR claim.

CI checks the executable route inventory on every push and pull request. Any new
or changed executable/workflow requires explicit review and a refreshed inventory.
This detects drift; it is not a security sandbox. Protect the branch and require
this CI check before merging. Never refresh the baseline blindly to make CI green.

Fully identified individual Story operations may be reconciled after approval
expiry without uploading or creating anything. New delivery always needs current
approval. Ambiguous and grouped operations retain their explicit recovery paths.

No claim of deployment is valid until this branch is merged and active callers
use the updated publisher. Old pinned external code is outside this local gate.
