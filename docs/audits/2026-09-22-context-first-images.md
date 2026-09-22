# Context-first image selection

Owner direction: start at the news article and verified official website, fill
remaining needs from the source best suited to the subject, remember outcomes,
and permit relevant image reuse instead of forcing unrelated variety.

## Implemented flow

After timing and entity resolution, reuse the already-fetched article HTML.
Extract declared Open Graph / NewsArticle images and in-article figure images;
ignore ordinary navigation and advertising images. Resolve the official website
from the exact encyclopedia entity's Wikidata P856 (not an invented model URL).
Inspect that website and at most two same-site news/media links. Existing verified
media-album adapters, including Ceer, remain available.

Primary image downloads have byte, format and resolution checks, bounded timeouts,
HTTPS-only public-host validation and at most two same-site redirects. Known
publisher/NASA CDNs use fixed source-verified hosts. Arbitrary private-network
URLs and credential-bearing URLs are rejected. Copyright metadata is retained;
the owner's editorial-use decision is not represented as a copyright license.

If primary sources are insufficient, route astronomy subjects toward NASA and
historical objects toward the Met, then general catalogs. Previous successful
providers rank fallback choices. Two relevant images can support a three/four-card
package, so a primary pool need not trigger unrelated searches solely for variety.

A budgeted Sonnet pixel preflight checks up to five source images before paid
research/writing. It validates the actual subject and rejects lookalikes. One
bounded refill skips rejected images and tries the next available source. Full
independent final pixel/card review remains mandatory.

`autopilot-image-memory` persists per-entity, per-image accepted/rejected results
and provider outcomes. Rejections expire after seven days and never globally
blacklist an image. Up to 300 entries are retained. Final review image rejections
also update memory. Production and diagnostic runs share that journal and their
existing single concurrency group.

A source image may appear on at most two editorial cards if relevant to both.
Credits headers are excluded from the reuse count. Repeated whole rendered cards
remain prohibited. The design and rendering dimensions are unchanged.

## Validation and boundaries

Regression tests cover source extraction, primary-before-stock ordering,
official-site identity, private URL rejection, expiring scoped memory, early
pixel rejection, source binding, retained rights metadata and bounded reuse.
The old no-reuse tests now enforce three-use rejection.

A read-only live check of https://aawsat.com/node/5321098 extracted and downloaded
the original publisher image at 1200x800. Visual inspection showed the financial
district, suitable for Saudi-investment context; it must not be called BlackRock's
headquarters. No paid generation was used for this check.

Websites that block retrieval or expose images only in unsupported interactive
formats may still need another source. Preflight model quality and full package
completion require a subsequent paid end-to-end trial; offline tests and this
single live extraction do not establish autonomous publishing readiness.
