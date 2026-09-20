# Public image pool recovery — 20 September 2026

## Root cause and change
The recovery collector stopped after five review-eligible images. The renderer then excluded attribution-required images, so a full review pool could produce an empty public pool without reaching later search pages.

Production now constructs Sources with publication_only=True. Both recovery and ordinary image search filter with the same image_without_public_credit predicate used by publication before counting accepted images. Recovery also excludes these assets before consuming download attempts. The current Flickr adapter returns only CC BY 2.0, so public-mode recovery skips that stage; review-mode Flickr and CC BY support remain available.

No request/download/pool limits were increased. No topic broadening, weaker relevance or license rules, permanent source-photo storage, paid AI calls, package generation, or public posting.

## Validation
- Two regression failures reproduced the empty public pool despite three eligible later-page assets. Both pass after the fix.
- A further failing assertion reproduced unnecessary Flickr requests in public mode; now passes.
- 3 new pool tests, 10 existing multi-source tests, and 12 subject-resolution tests passed (25 focused tests). git diff --check passed.
- Independent review of the core change and Flickr follow-up found no blockers.
- Free live provider probes examined only PepsiCo and The Shawshank Redemption. These probes started before the Flickr skip was added; they are evidence about provider availability, not an end-to-end verification of the final configuration.

- Live result: PepsiCo returned 2 download-verified eligible images (two factory photographs); The Shawshank Redemption returned 0. Neither meets the existing three-image pre-draft gate. No pixel reviewer was run; matching metadata and successful download do not establish visual suitability.

## Remaining work
This fixes premature pool exhaustion, not the supply of eligible images for every topic. Do not claim a complete autonomous package or schedule readiness. Before another paid package run, identify enough topic-relevant public-eligible visual options, or implement a reviewed attribution/alternative-licensing solution. Sources cards remain review-only.
