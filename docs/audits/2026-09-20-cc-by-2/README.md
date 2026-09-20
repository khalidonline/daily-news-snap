# Separate-subject / CC BY 2.0 validation — 2026-09-20

Implementation: PR #221. This audit uses public HTTP retrieval and local image/credits rendering only. Paid AI calls: **0**. Nothing published.

## Result

| Separate query | Production pool | Download/decode | Complete credits layout |
|---|---:|---:|---:|
| Jose Mourinho | 2 | 2 passed | 2 passed |
| Diego Simeone | 0 | No eligible candidate | Not applicable |

Mourinho asset IDs: 29365429 and 29365430. Both are CC BY 2.0, credited to Ronnie Macdonald, dated 2013. These are historical photographs, not evidence of a current event. Both credits together also fit one frame (21 lines, bottom at 1370 of 1920 pixels). A rendered credit frame was visually inspected.

Simeone's sampled CC BY 2.0 portrait 64166987 is 588 × 785, below the size gate. Asset 64166626 lacks the required subject-name match in metadata. Other sampled files fail existing licensing/restriction/size gates. This is a bounded search result, not proof that no suitable photograph exists anywhere.

The first production-pool probe returned no eligible images and recorded an ImageSourceError on Mourinho. A single diagnostic rerun returned the two eligible Mourinho photographs and no API errors; exact queries and IDs are retained in production-pool.json. Network/source variability remains possible; no paid retry was needed.

## Implemented behavior

- Editor specifies one or two entity names; research resolves each separately from retrieved encyclopedia titles and preserves source IDs. Unresolved explicit subjects hold the candidate.
- Image preflight searches each verified name separately and requires coverage for every named subject. It does not relabel another person as the missing subject.
- Exact CC BY 2.0 and CC BY 4.0 license URLs are validated against their version. Mixed versions get individual license labels and links.
- Credits retain supplied author, title, credit text, original-work links, copyright/attribution notices, usage terms and disclaimers. Oversized/incomplete credits fail closed. Additional restrictions and BY-SA remain unsupported.
- Attributed images require the credits in the same delivery video. Cropping/resizing is disclosed. A successful image-only probe does not authorize publishing.

License reference: https://creativecommons.org/licenses/by/2.0/legalcode (section 4).

## Evidence and remaining work

- results.json: separate direct searches, offsets 0/5/10, source metadata and individual gate results.
- production-pool.json: bounded runtime search queries, final pools, download/decode and credits checks.
- direct_probe.py: free direct-search diagnostic; run from repository root with PYTHONPATH=.
- Existing 210 v2 tests and 15 focused tests passed locally. Final PR CI is the merge gate.

The two-person rivalry package remains held for missing Simeone coverage and insufficient overall visual variety. Next: obtain a properly licensed, sufficiently large, verified Simeone source or select a different image-feasible angle; then run a fresh reviewed package. Do not rerun paid drafting for this unchanged image pool. Automatic 08:00 posting is not qualified by this audit. Budget configuration and settled AI balance ($3.286369 at the last reconciliation) were not changed.
