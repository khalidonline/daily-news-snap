# Unpaid source audit — 2026-09-20

Scope: reproduce the final trial's exact query, then query its two named subjects separately. Live Commons API adapter results at offsets 0, 5 and 10; five files per page. No paid AI calls. This is a sample of returned metadata, not a pixel review, complete Commons inventory, or historical reconstruction of every previous candidate.

| Query | Returned | Existing rights pass | Size pass | Subject metadata pass | All pass |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jose Mourinho Diego Simeone rivalry | 0 | 0 | 0 | 0 | 0 |
| Jose Mourinho | 15 | 1 | 14 | 14 | 0 |
| Diego Simeone | 15 | 3 | 11 | 14 | 0 |

The combined query retrieved one encyclopedia title, Diego Simeone, but cannot resolve that whole two-person rivalry query to this one person without changing its meaning. The individual queries resolved to José Mourinho and Diego Simeone with source IDs.

Across the 30 individual-name results: 21 CC BY-SA (3.0/4.0), four CC BY 2.0, one CC BY 4.0, four public-domain. The existing publisher supports neither BY-SA nor BY 2.0. All four public-domain results fail the current 600px short/1000px long dimension threshold. The BY 4.0 image (159786471) has valid-looking attribution fields but restrictions=personality, which the existing guard rejects. Do not label this a missing-credit bug or remove that flag automatically.

Evidence: raw results.json and attribution-rejection.json alongside this report. API retrieval succeeded for the sampled queries: this sample does not support blaming connectivity or asserting no relevant photographs exist.

Official licence terms consulted:
- https://creativecommons.org/licenses/by/2.0/ — attribution, licence link, applicable change notices, no added restrictions; supplied title/credit information matters.
- https://creativecommons.org/licenses/by-sa/4.0/ — includes ShareAlike; not interchangeable with BY-only handling.

Next bounded implementation recommendation:
1. Represent/query each verified named subject separately (and preserve the editorial relationship), rather than a combined rivalry search or automatic guessed truncation.
2. Add end-to-end CC BY 2.0 handling with exact version, required credits/notices and delivery validation. This is NOT clearance of all four sampled images; inspect their remaining metadata and actual pixels.
3. Keep BY-SA and personality-flagged cases outside automatic approval until their obligations are explicitly handled. Keep the image quality threshold for now.
4. Re-run a free image-only feasibility probe before spending on story generation. A new paid image supplier is not yet shown necessary by this sample.

No production changes, budget increases or publishing during the audit.
