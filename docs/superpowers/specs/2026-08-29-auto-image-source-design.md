# Automatic Relevant Image Source Design

## Goal

Make the daily Snapchat news bot choose a relevant image without pinning production runs to SPA or any other single provider.

## Audience intent

The image must explain or depict the selected story. Source identity is secondary to subject relevance, safety, licensing, and usable quality.

**Binding rule:** best relevant image wins; source is secondary.

## Approved behavior

- `auto` is the default image mode for scheduled and manual daily-news runs.
- `auto` does not force SPA, Commons, Pexels, or another provider to the front through the workflow input.
- The existing approved providers remain available: local licensed library, original article image, SPA, Wikimedia Commons, Library of Congress, Openverse, and Pexels.
- Each provider still applies its existing metadata, licence, safety, geographic-context, graphic/document, minimum-score, and cooldown checks before a candidate can be considered.
- A candidate that survives those checks is then judged visually against the selected story using the existing `photo_shows()` vision relevance gate.
- In `auto` mode only a `yes` verdict is accepted. `neutral` and `no` both continue to later providers.
- `yes` means the photo directly depicts a person, place, company/product, object, or scene named by the story strongly enough that a viewer can understand the connection without explanation.
- `neutral` is intentionally not used for normal daily-news cards. A generic related image is weaker than either a directly relevant image from another source or no image.
- The first `yes` candidate may be accepted because all `yes` verdicts satisfy the same direct-relevance standard; provider order therefore acts only as a tie-breaker inside the highest relevance tier.
- If no provider yields `yes`, the selector continues to later ranked story candidates under the existing `REQUIRE_PHOTO` behavior rather than publishing a weak image.
- Existing recent-image fallback behavior remains unchanged; no safety or relevance threshold is lowered to force a card.
- SPA remains useful for Saudi official/national stories but is not the universal default.
- Manual provider choices remain available only as troubleshooting/curation overrides and keep the legacy provider-priority behavior.
- `none` remains available to intentionally disable image fetching.
- `pexels` continues to normalize to the existing internal `stock` provider name.

## Story context used for relevance

The visual judge must receive the selected story's `headline`, `summary`, and `takeaway`, not only search keywords. `daily_news_runner` keeps an internal mapping from the model's English/Arabic image-query tuple to this story context. The local provider is called first for every story, so it can establish the current story context for the subsequent provider wrappers without changing `news_bot.py`.

## Safety and quality constraints

Do not weaken any existing blocked-image terms, artwork/document rejection, Saudi-context requirements, minimum term hits, minimum photo score, recent-image deduplication, licensing/credit handling, or photo readability checks.

A wrong image is worse than no image.

## Workflow UX

The `image_source` workflow input should offer:

1. `auto` — recommended/default
2. `article`
3. `spa`
4. `commons`
5. `loc`
6. `openverse`
7. `stock`
8. `none`

Scheduled runs use `auto` when no manual workflow input exists.

## Implementation boundary

Keep `news_bot.py` unchanged. `daily.yml` already enters through `daily_news_runner.py`, so the runner will:

1. normalize the workflow/environment image mode;
2. retain each returned story's text context after summarization;
3. wrap the existing provider fetch functions only when `IMAGE_SOURCE=auto`;
4. let every provider run its existing fetch/safety/licence/score/cooldown logic unchanged;
5. call `photo_shows()` on any candidate returned by a provider;
6. return the candidate to the legacy first-success loop only when the vision verdict is `yes`; otherwise return no photo so the loop continues.

This preserves the existing renderer, publisher, provider implementations, photo cooldown, and breaking-news behavior.

## Tests

Add deterministic tests proving:

- no `IMAGE_SOURCE` environment variable => `auto`;
- `IMAGE_SOURCE=spa` remains `spa` as an explicit override;
- `IMAGE_SOURCE=pexels` becomes `stock`;
- unsupported values fall back to `auto`;
- workflow default and scheduled fallback both use `auto`;
- an early `neutral` candidate is withheld so a later `yes` candidate can win;
- an early `no` candidate is rejected;
- a `yes` candidate is returned with its original credit/domain metadata unchanged;
- the visual judge receives headline + summary + takeaway context;
- explicit manual provider mode does not install the automatic relevance wrappers.
