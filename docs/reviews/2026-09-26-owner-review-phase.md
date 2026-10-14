# Owner review phase — 2026-09-26

Owner decision: Silent Hill and Apple (26 Sep) stay as published; their saved
replacements are NOT to be published. Lessons go into future packages instead.

Lessons applied to writer, text_review and reviewer prompts (OWNER_REVIEW_LESSONS):
- Place/entity type copied exactly from the source (St. Amelia is a coastal town, not an island).
- First mention of a team/company in a card is named (no bare «الفريق»).
- Exact title spelling and punctuation (P.T.).

Review phase (the owner reviews the first three packages before publication):
- Daily trigger (push to autopilot-trigger.txt) runs shadow for both lanes.
- Owner reviews in chat, not Telegram. For each passed lane the workflow saves a
  downscaled review sheet (journal review-sheet-<slot> on snapchat-api-state),
  built only from cards whose hashes match the approval seal.
- `python review_package.py daily|local` prints the sealed text and writes the sheet
  (git only; no API, model calls or image downloads).
- Approval = run "Auto-publish reviewed Snap packages" (workflow_dispatch, lane
  both/daily/local). It publishes only today's sealed package; no regeneration.
- End the phase: set repository variable AUTOPILOT_OWNER_REVIEW=0.

Digits: owner chose Western digits (1999) inside card text (26 Sep). Enforced in the
writer prompt and at render (western_digits); story counters are unchanged (١ من ٣).
