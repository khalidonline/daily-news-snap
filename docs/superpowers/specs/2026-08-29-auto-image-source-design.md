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
- Relevance tiers outrank provider order:
  1. `yes` — directly depicts a person/place/object named by the story; accept.
  2. `neutral` — genuinely related but less direct; keep as fallback while continuing to search for `yes`.
  3. `no` — misleading, wrong subject/place, graphic/document, or unrelated; reject and continue.
- Provider order is only a tie-breaker among candidates in the same relevance tier. In normal `auto` mode it must never cause a `neutral` image to beat a later `yes` image.
- The first `yes` candidate may be accepted because all `yes` verdicts satisfy the same direct-relevance standard; this avoids unnecessary network and vision calls after the highest relevance tier has already been reached.
- If no provider yields `yes`, the first safe `neutral` candidate may be used after all relevant providers have been checked.
- If no fresh `yes` or `neutral` image exists, preserve the existing recent-image fallback behavior rather than weakening relevance/safety checks.
- SPA remains useful for Saudi official/national stories but is not the universal default.
- Manual provider choices remain available only as troubleshooting/curation overrides and keep the legacy provider-priority behavior.
- `none` remains available to intentionally disable image fetching.
- `pexels` continues to normalize to the existing internal `stock` provider name.

## Story context used for relevance

The visual judge should receive the selected story's `headline`, `summary`, and `takeaway`, not only search keywords. `daily_news_runner` may keep an internal mapping from the model's image-query tuple to this story context so the large legacy `news_bot.py` selection block does not need to be restructured.

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

Keep `news_bot.py` unchanged if possible. `daily.yml` already enters through `daily_news_runner.py`, so the runner can:

1. normalize the workflow/environment image mode;
2. retain story text context after summarization;
3. wrap the existing provider fetch functions only when `IMAGE_SOURCE=auto`;
4. force the legacy first-success loop to continue past `neutral`/`no` candidates and return only a `yes` candidate, or the best neutral fallback after the provider chain is exhausted.

This preserves the existing renderer, publisher, licences, provider fetchers, photo cooldown, and breaking-news behavior.

## Tests

Add deterministic tests proving:

- no `IMAGE_SOURCE` environment variable => `auto`;
- `IMAGE_SOURCE=spa` remains `spa` as an explicit override;
- `IMAGE_SOURCE=pexels` becomes `stock`;
- unsupported values fall back to `auto`;
- workflow default and scheduled fallback both use `auto`;
- an early `neutral` candidate does not beat a later `yes` candidate;
- an early `no` candidate is rejected;
- if no `yes` exists, a safe `neutral` candidate is restored after the source chain is exhausted;
- a selected candidate keeps its credit/provenance marker;
- explicit manual provider mode does not install the automatic cross-source relevance wrapper.
