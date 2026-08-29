# Automatic Relevant Image Source Design

## Goal

Make the daily Snapchat news bot choose a relevant image without pinning production runs to SPA or any other single provider.

## Audience intent

The image must explain or depict the selected story. Source identity is secondary to subject relevance, safety, licensing, and usable quality.

## Approved behavior

- `auto` is the default image mode for scheduled and manual daily-news runs.
- `auto` does not force SPA, Commons, Pexels, or another provider to the front through the workflow input.
- The existing image pipeline remains responsible for story-specific relevance and safety checks.
- The original article image remains the strongest direct-context candidate when usable because it is attached to the selected article itself.
- Other approved sources remain available through the existing chain: SPA, Wikimedia Commons, Library of Congress, Openverse, and Pexels.
- SPA remains useful for Saudi official/national stories but is not the universal default.
- Manual provider choices remain available only as troubleshooting/curation overrides.
- `none` remains available to intentionally disable image fetching.
- `pexels` continues to normalize to the existing internal `stock` provider name.

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

Because `daily.yml` already enters through `daily_news_runner.py`, enforce the default there and in workflow configuration without restructuring the large `news_bot.py` image pipeline.

`daily_news_runner.configure()` should set `news_bot_module.IMAGE_SOURCE` from the environment, defaulting to `auto`, and preserve explicit supported overrides. Invalid/blank values fall back to `auto`.

## Tests

Add deterministic tests proving:

- no `IMAGE_SOURCE` environment variable => `auto`;
- `IMAGE_SOURCE=spa` remains `spa` as an explicit override;
- `IMAGE_SOURCE=pexels` becomes `stock`;
- unsupported values fall back to `auto`;
- workflow default and scheduled fallback both use `auto`.
