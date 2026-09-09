# News Visual Recovery Design

**Status:** Approved by user on 2026-09-09.

## Goal

An editorially approved News story must never be dropped only because its first
image searches fail. Every scheduled News card must use a relevant real photo,
an exact organization logo, an exact named-person portrait, or a pre-approved
contextual photograph. AI-generated imagery is not allowed.

## Required outcome

- Keep the highest-ranked editorial story fixed while resolving its visual.
- Remove the normal `no card: ... had a usable photo` outcome.
- Do not switch to a weaker story merely because it is easier to illustrate.
- Preserve all existing editorial, licensing, safety, attribution, cooldown,
  graphic-quality, geographic, product-model and identity protections.
- Prefer a fresh visual, but allow controlled reuse of an approved exact-subject
  asset rather than miss the News card.

## Visual resolution ladder

Resolve the selected story through these tiers, stopping at the first verified
candidate:

1. Exact article or event photograph.
2. Official press photograph from the named organization or event.
3. Exact portrait of the named public person.
4. Exact organization, company, product-family, club or institution logo.
5. Exact subject photograph: headquarters, venue, named place, product or
   physical object explicitly present in the story.
6. Metadata-matched licensed contextual photograph.
7. Previously approved visual tied to the same exact entity or context class.

A candidate judged unrelated is never promoted. A logo is valid only when it
matches a named entity in the story. A portrait is valid only when full identity
can be established from an official page or high-confidence metadata. A numbered
product requires the exact model; otherwise use the manufacturer, venue or logo
instead of an older product.

## Subject-aware query planning

Before image search, derive a small ordered visual plan from the selected story:

- `event`: the exact announcement, match, launch or incident;
- `people`: named public figures suitable for portraits;
- `entities`: companies, ministries, clubs and institutions suitable for an
  official photograph or exact logo;
- `places_objects`: named locations, products and physical subjects;
- `contexts`: concrete activities or environments that honestly illustrate the
  story without claiming to show the event itself.

Use deterministic extraction from the headline, summary, source item and image
queries first. The existing editorial response may supply additional visual
targets, but it cannot override identity or safety gates.

## Search architecture

The resolver searches existing approved providers plus a persistent approved
visual catalog. Providers remain responsible for licensing and download safety.
The resolver is responsible for source ordering, identity checks and promotion.

For each visual target, try:

- article and official source;
- approved local catalog;
- SPA for Saudi subjects;
- Wikimedia/Wikipedia/Commons;
- Library of Congress where relevant;
- Openverse;
- Pexels when the credential is healthy.

Provider failure is isolated. A 403, rate limit, missing image or timeout moves
to the next provider or target and cannot terminate the card.

## Approved visual catalog

Add a durable catalog of reusable, already-verified assets. Each record stores:

- local asset path;
- visual type: photo, portrait or logo;
- exact entity aliases in Arabic and English;
- optional context classes;
- source and required attribution;
- licence and provenance;
- identity confidence;
- last-used timestamps by bot;
- restrictions such as exact product model or historical date.

The catalog starts with existing approved local assets and expands whenever a
new candidate passes verification. Exact-subject reuse may bypass the ordinary
freshness cooldown only at the final recovery tier. Reuse never crosses entities,
and the resolver rotates among multiple approved assets when available.

## Validation policy

- **Photos:** metadata must match a visual target; the existing vision gate must
  return `yes`, or `neutral` only for narrowly allowed metadata-backed contexts.
- **Portraits:** require full-name identity from an official or authoritative
  subject page; never infer identity from facial similarity alone.
- **Logos:** require exact normalized entity-name equality and reject unofficial,
  obsolete or parody marks. Render logos with a clean neutral photographic or
  branded card treatment rather than stretching a small logo as a photograph.
- **Products:** exact numbered model is mandatory for a product photo. When none
  exists, fall back to the exact company, headquarters, launch venue or logo.
- **Context photos:** must depict a concrete subject named or directly implied by
  the story. Generic city, traffic, money, office, stadium or landscape images
  remain blocked unless that setting is itself the story.

## Failure handling

The selected story stays fixed through all tiers. If live providers are
unavailable, use the approved catalog. If an unknown subject has no exact asset,
use a verified contextual class derived from a concrete story subject. The run
fails only for an infrastructure error that prevents rendering or delivery, not
for ordinary image scarcity. Notifications must report the actual infrastructure
failure rather than saying that no story had a usable photo.

## Cost and reliability

- Reuse existing editorial output; do not add a second expensive text-model call.
- Cache provider results and identity decisions.
- Stop paid vision checks once a candidate is accepted.
- Keep Pexels optional; its current 403 cannot affect delivery.
- Prefer deterministic metadata and catalog checks before paid vision.

## Testing and observability

Regression coverage must prove:

- the 2026-09-09 four-story run produces a card using the exact Claude/Anthropic
  visual path instead of reporting no card;
- the top-ranked story is not replaced solely for image convenience;
- exact portraits and logos are accepted;
- wrong people, organizations and numbered products are rejected;
- provider outages fall through to the next tier;
- approved exact-subject reuse works after fresh sources fail;
- reuse cannot leak across stories or entities;
- generic finance, city, traffic, stadium and landscape imagery remains blocked;
- the scheduled workflow cannot finish successfully without a rendered card;
- logs state which visual tier and source won, why candidates were rejected, and
  whether the final asset was fresh or reused.

## Scope

This change applies to the scheduled News workflow. Topic and Story keep their
current visual policies. Direct Snapchat publishing remains disabled; cards
continue going to Telegram for review.
