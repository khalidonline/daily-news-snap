# Encyclopedia retrieval diagnosis and recovery

The owner instructed continuing through diagnosis, repair and end-to-end
verification without stopping after every patch. Shared cap remains $3/day.

Read-only GitHub probe 35586187276 retrieved Cole Palmer and Moringa peregrina
successfully in the actual runner. Thus the earlier empty titles are not proof
of absent/ambiguous subjects; their original failure was swallowed and cannot
be retrospectively assigned a certain transport cause.

The probe established an independent concrete defect: every extract request
sent exchars=10000, while Wikimedia warned the allowed maximum is 1200. Returned
histories were only 1208/1211 characters. Official API documentation:
https://www.mediawiki.org/wiki/Extension:TextExtracts#API
Removing that parameter retrieved 19682 characters for Cole Palmer. The adapter
now retains its existing local 10000-character bound; Moringa returned 4318.
Exact title/redirect provenance and identity checks are unchanged. Search uses
exintro and an explicit exlimit equal to the bounded requested page count.

Added at most one retry for transport timeout/URLError, HTTP502/503/504 and
API maxlag/readonly. No retry for HTTP403/429 or permanent API errors. API errors
are raised instead of treated as an empty search. English retrieval failures
persist error class and HTTP status, distinct from a genuinely unresolved name.
Native-name fallback and final factual/image/publication gates remain unchanged.

Five initial tests reproduced truncation, absent retry and misleading empty
results; configured suite passed293. Independent review requested explicit
multi-extract count, covered by an additional failing-then-passing regression.
All six retrieval tests pass. Final GitHub CI must pass before merge. Updated
credential-free probe reruns on merge to verify the corrected adapter on runner.
No paid AI calls were made during this diagnosis/implementation.

Remaining: verify runner retrieval, then use a bounded fresh shadow trial toward
the full package. Neither this patch nor offline tests establish visual design
approval or current-engine autonomous readiness.
