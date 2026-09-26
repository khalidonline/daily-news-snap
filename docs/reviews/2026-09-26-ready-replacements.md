# Apple and Silent Hill replacement packages

User authorized corrections, deletion of the two existing packages and replacement on 2026-09-26 at 12:43 Asia/Riyadh.

## Prepared and pixel reviewed
- Apple: `approved/apple-revision-20260926/manifest.json`, 2 cards (Info + Topic, not mislabeled as a story). Identity `784b107b251ac5d2d101e08dde6d288fa931c343cb60115c9e6f6b4def729138`.
- Silent Hill: `approved/silent-hill-revision-20260926/manifest.json`, 4 cards (Info + 3 numbered story cards). Identity `169e3ba0f092c60431050bf253788afee351cc4f815517a09ca9c84e3b849693`.
- Original story template, Arabic counters, badges and red closing retained. Internal credits are excluded from both manifests.
- Existing appropriate Apple and Townfall photos reused. Two exact archival game screenshots were checked against installment/date and bound to the owner's existing editorial-use authorization. This does not assert a copyright license or trust all assets on that archive.
- All changed text rendered locally; no paid model/image API requests. Additional model API cost $0. ChatGPT usage and subscription charges are not measured by this ledger.
- 11 primary-image tests passed; exact archive pairs additionally verified to reject absent authorization, forged identity, alternative asset and alternative page.

## Required before any delivery
The Bundle API spec explicitly says DELETE /post removes the Bundle record, NOT the published social post. Do NOT call this a Snapchat deletion, and do NOT set predecessor reconciliation DELETED from a Bundle deletion alone.
Source: https://api.bundle.social/swagger-json (post.delete).
Snapchat profile management currently shows a sign-in form; no authenticated deletion occurred.
Read-only capacity check run https://github.com/khalidonline/daily-news-snap/actions/runs/36233882509 confirmed 8 used, 20 limit, 12 remaining; replacements require 6. Recheck before delivery.
The old 8 cards remain published. Both replacements are READY_AWAITING_CONFIRMED_SNAPCHAT_DELETION. No replacement post has been created.
Keep prior journals intact. After verified native Snapchat deletion, archive the exact 4 old post IDs for each package with evidence and set its predecessor reconciliation to DELETED. Validate each review.json manifest/spec digest, expiry, image hashes, predecessor status and fresh quota. Then publish one package per run with the existing publisher and shared concurrency, no regeneration.
Both manifests expire midnight Saudi on 2026-09-27; no automatic expiry extension.
