# Fresh multi-source recovery — 2026-09-20

Implementation: PR #222. Public source requests and local deterministic checks only; **0 paid AI calls**, no publication, no new subscription or budget change.

## Final observed coverage

These counts describe downloaded/decoded candidates passing source rights and metadata checks. They do not establish final crop quality, editorial relevance, or approval to publish.

| Topic | Candidates | Sources | Observation |
|---|---:|---|---|
| Jeddah | 5 | Commons search + dedicated collection | Collection retrieval supplied three candidates absent from the first search page. |
| iPhone | 3 | Commons | Later pages recovered three candidates after first-page licensing exclusions and source failures. |
| Date palm | 2 | Commons + Flickr | Independent second source contributed one candidate. |
| Saudi coffee | 1 | Flickr | Final tightened search recovered “Saudi Coffee,” Flickr 52578239478, CC BY 2.0, Ken Bosma. |
| Diego Simeone | 0 | All recovery stages attempted | Still limited by rights, small originals, empty Flickr result and intermittent source failures. |

Initial coffee results included a market portrait and Swedish café sign because the old metadata filter joined distant words in descriptions. They were **not approved**. The final code requires subject terms to occur close together, and excludes both. Initial raw results are retained for audit; `final_metadata_pass_ids` identifies which rows survive the new filter. `saudi-coffee-final.json` supersedes the initial coffee result. `diego-simeone-final.json` records the final small-original filter test.

## Behavior delivered

- Production explicitly enables fresh recovery at subject preflight. No cross-run local image library.
- Searches Commons, the subject's direct Commons category, and public Flickr search/photo pages. Two further Commons pages remain available if needed.
- Flickr search is only discovery. Each selected photo page must agree on photo identity and CC BY 2.0 in its embedded model and structured ImageObject. JavaScript is never executed. Exact Flickr page/image hosts are allowed; arbitrary hosts and redirects remain rejected.
- Source captions are prefiltered before fetching Flickr photo pages. A cheap proximity check removes incidental distant-word matches. Category association remains metadata evidence, not pixel approval.
- Checks real downloads and decoding before paid drafting. A failed thumbnail can fall back to an original rendition of the same asset. Known undersized originals are rejected without wasting download requests.
- Up to five candidates, five discovery stages, ten candidate download attempts (at most two renditions each), and a 90-second soft deadline checked between requests. A Flickr search may fetch up to five photo pages. Individual requests retain size/time bounds. The deadline can be exceeded by the final in-flight request.
- Source URLs, credits, rights metadata, image hashes and shared-original IDs travel with the package; image bytes are discarded after preflight. Render source photos use a temporary directory removed on success or failure. Final review cards/video remain normal workflow artifacts, not a reusable source-photo bank.
- Renderer uses the download-verified pool. Cross-provider copies with the same original Flickr ID are rejected as duplicate source images. Supported attribution travels in the same final video.
- Images are explicitly described as subject illustrations unless event/date context is reviewed. Existing Saudi-language, editorial, pixel-review and publication gates remain.

## Validation

- 225 v2 tests passed locally before the final proximity regression; 21 focused tests passed including that regression. Final PR CI passed, including offline checks, layout checks and the isolated container; PR #222 merged.
- Tests cover second-source recovery, original-rendition recovery, complete Flickr attribution, identity/license disagreement, exact host validation, metadata-only caching, duplicate originals, source-file cleanup on error, verified-only render catalogs, known-small-original filtering, and misleading caption mentions.
- Live source metadata and diagnostic counts are in the JSON files alongside this report. Photos are not committed. `probe.py` reproduces a free five-topic probe from the repository root with `PYTHONPATH=.`; it writes metadata reports only.

## Limits and next checkpoint

This is a working two-provider implementation, not universal image coverage. Openverse returned HTTP 403 / timeout in this environment and was not integrated as a dependency. Flickr public-page metadata can change or time out; such failures reject the result and recovery continues. No Getty access, press-library permission, or paid license was assumed.

The next checkpoint is broader licensed/source coverage or adaptive small-portrait layout, followed by an actual reviewed fresh package. Simeone remains unresolved, and coffee/date-palm pools are smaller than the current three-image preflight target. Do not spend paid drafting on those unchanged insufficient pools. Automatic 08:00 posting is not qualified by this image audit.

References:
- https://www.flickr.com/creativecommons/
- https://www.mediawiki.org/wiki/API:Categorymembers
- https://creativecommons.org/licenses/by/2.0/legalcode
