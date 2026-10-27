# Fixed template candidate — 27 October 2026

This is a new reusable code template, not another regenerated branded image.
It is NOT an approved publication package. Do not publish it or replace the
existing design master until Khalid approves the actual preview and changed copy.

- Exact 1080x1920 PNG; palette reads the canonical design-settings.json.
- Almarai Regular is the explicit proposed font asset, not a recovered reference
  font. Header 36px, title 52px, body 47px, captions 28px, closing 44px, CTA 40px.
  Owner correction: all bullet lines, including continuation lines, align right
  at x980. Other text alignment is unchanged.
  Latest preview is an explicit owner comparison, top to bottom: 46 Regular,
  45 Regular, 45 Bold, 44 Bold. It does not change the global 47 Regular default.
  The preview restores the original curved sharing icon directly from the
  approved source panel; generic template fallback is curved too.
- Real Arabic glyph bounds are checked before export; two lines maximum, no
  automatic shrink, overlap, truncation or removal of CTA. Native line spacing
  is 1.5 to keep Arabic ascenders and descenders separate.
- Two equal-height photo panels; fixed header, 4 body slots, closing and sharing
  strip. CTA bottom 1720, nonessential footer logo bottom 1810.
- Source photograph panels are retained from the previously approved Oxford
  composition. All headlines and copy remain in render.py for review.
- Source facts: OSDC confirms permanent traffic removal began 26 October 2026;
  temporary design changes/transition should not be confused with temporary ban.
- Shortened title and body copy need owner approval. No publication approval,
  successful platform overlay review or destination receipt is fabricated.

Reproduce from repository root:
`PYTHONPATH=. python drafts/oxford-fixed-template/render.py`

Verification: actual Oxford PNG passes palette and native line geometry checks.
Latest full-suite run: 1112 passed, 92 failed, 21 errors; failure names are retained in
full-suite-known-failures.txt. Final focused gate/template/inventory suite:
33 passed. Existing unrelated suite failures still prevent claiming
a green project or a live deployment. This preview does not publish anything.

After approval: seal the exact PNG, current settings and font hashes in the
delivery package, then follow the shared publisher. No live calls from rendering.
