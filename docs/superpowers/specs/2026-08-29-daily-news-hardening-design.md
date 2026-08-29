# Daily News Hardening Design

**Status:** Approved by user after review of News brief runs #86 and #87.

## Goal

Make the daily Saudi Snapchat brief reliably stay inside the intended scope for Saudi Arabic-speaking adults aged roughly 25–50, while still producing a card when a safe and reasonably relevant photograph exists.

## Evidence from production

Run #86 selected a foreign political/geopolitical story about Trump and Venezuelan oil as the first story. The same ranked set also included a routine الهلال match result and an obscure-company financing story about Lambda. These violate the intended editorial scope even though the system prompt already says to reject politics/conflict, routine sports results, and obscure-company stories.

Run #87 showed that the new image relevance gate correctly rejected misleading images, but the `yes`-only rule rejected every safe `neutral` candidate and caused the whole run to produce no card. Run #87 also ranked out-of-scope health advice and the Lambda financing story, confirming that prompt-only scope enforcement is insufficient.

The run logs additionally exposed two ingestion/operations issues: the الوطن حياة RSS feed is currently malformed for strict XML parsing, and Pexels returns HTTP 403 for the configured credential. Pexels must remain optional and must never determine whether a run can publish.

## Editorial hard boundaries

The deterministic daily-news gate must reject these before lane allocation:

- foreign political/geopolitical stories whose main subject is a political leader, election, diplomatic dispute, sanctions/control dispute, war/conflict, or similar political event, unless the input itself states a direct Saudi/Gulf policy or consumer/economic consequence;
- medical/health advice and disease-treatment content; a nationally significant Saudi health-policy, insurance, pricing, or service change may still qualify under `saudi_core`;
- routine weather forecasts/alerts unless the story is fundamentally about material travel/service disruption rather than the weather itself;
- ordinary sports results, scorelines, routine wins/losses and match recaps; championships, finals, historic qualification, major records and genuinely exceptional decisions remain eligible;
- financing/fundraising/borrowing stories whose primary subject is an unfamiliar global company and whose relevance comes only from a large dollar amount or a famous supplier/investor name.

The existing hyperlocal, routine PR and routine fixture filters remain.

Macro-economic stories such as Federal Reserve rate decisions, inflation, oil-price/production changes and major market moves may remain eligible when they have plausible Saudi financial/consumer relevance. A political name or remote geography must not by itself make a story eligible.

## Two-stage editorial enforcement

1. **Pre-model:** hard-scope filtering happens before balanced lane allocation, so weak/out-of-scope stories do not consume the 60-item model window.
2. **Post-model:** returned stories are validated against the exact numbered shortlist item they reference. Invalid item numbers or hard-ineligible source items are removed. The model cannot override a hard boundary.

If filtering leaves fewer than the requested candidate count, use the remaining valid ranked stories; do not reinsert rejected stories merely to fill a number.

## Image selection

In `auto` mode, source is secondary to relevance.

For each ranked story:

1. search the approved providers using their existing licensing, quality, safety, Saudi-context, cooldown and metadata rules;
2. judge each technically usable candidate against the actual story headline + summary + takeaway using the existing vision judge;
3. a direct `yes` candidate wins immediately;
4. retain the first safe `neutral` candidate while continuing to search later providers for `yes`;
5. if no provider produces `yes`, use the retained `neutral` candidate;
6. never use a `no` candidate;
7. preserve the selected provider's real credit/provenance and marker sidecars;
8. if no `yes` or `neutral` image exists, move to the next ranked story.

Manual source overrides retain their legacy behavior.

## Feed ingestion hardening

- Normal daily news requires a reliable publication timestamp, so undated/unparseable-age items should be dropped during feed ingestion rather than counted as recent and discarded later.
- On XML parse failure, retry after a conservative sanitation pass for illegal XML control characters and bare ampersands. If the feed still fails, log it and continue; one feed can never break a run.
- Keep official الوطن حياة in the registry if sanitation recovers it; otherwise its failure remains isolated and other feeds continue.

## Pexels degradation

Pexels remains an optional final source. Current Pexels documentation confirms the existing `Authorization: API_KEY` request format; HTTP 403 means the configured credential does not have access. The daily brief must remain fully functional without Pexels. No fallback may misattribute a non-Pexels image as Pexels.

## Other consistency fix

The workflow title should no longer say `أعمال وتقنية` now that the approved scope includes Saudi life, sports, entertainment and travel. Use the existing broad `ملخص تنفيذي - خبر` label consistently.

## Verification requirements

Regression fixtures must include the exact failure shapes from #86/#87:

- Trump/Venezuela political-control story rejected;
- routine الهلال five-goal league result rejected;
- blood-pressure medication advice rejected;
- Lambda borrowing $1B for NVIDIA chips rejected;
- Fed rate story remains eligible;
- major Saudi real-estate story remains eligible;
- major championship/qualification sports story remains eligible;
- direct Saudi health-policy/insurance change remains eligible;
- post-model hard-ineligible item is removed even if model ranks it first;
- later `yes` image beats earlier `neutral`;
- first safe `neutral` is used when all later candidates are `neutral`/`no`/missing;
- `no` is never used;
- neutral fallback preserves the correct provider credit and provenance marker;
- malformed RSS with a bare ampersand can be recovered;
- undated items never enter the daily candidate pool;
- all existing editorial/image regressions continue to pass.
