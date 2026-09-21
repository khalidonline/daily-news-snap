# Source-bound editor selection

The owner authorized continuing after daily shadow run 35578655764 stopped.
That run spent $0.067886 and produced no draft or publication. Its Jeddah
selection repeated the same name as `Roshn Front (Jeddah)` and
`Roshn Front, Jeddah`, and reformatted source punctuation in a verbatim quote.
Strict validation correctly rejected the inconsistent output.

The editor now selects `title` or `summary` from the candidate identified by ID
and supplies one subject name plus its original-language mention. The coordinator
retrieves the exact source field, derives the subject list from those entries,
and runs the unchanged strict binding validator before research. Model-authored
titles, quotes, duplicate subject lists, unknown fields and cross-candidate IDs
are rejected. Invalid selections remain candidate-local so the next ranked
selection can proceed. Legacy selections retain their existing strict validator.

The prompt also tells the editor to interpret relative dates using the article
timestamp and prefer explicit dates. This is guidance, not a new deterministic
timing guarantee; existing factual/timing review remains required.

Verification: four initial tests reproduced missing hydration and pipeline
failure, then passed. The configured full v2 suite passed 278 tests. Independent
review passed 10 focused tests with no blockers. A fifth new test verifies that
invalid source-field selection falls back to the next candidate; all five pass.
Offline evaluation reports `offline_ready`. GitHub CI is required before merge.

Image investigation: production logs after 08:37 UTC show only two accepted
distinct Cindy Crawford assets; the required minimum is three. Other results
failed rights, original size or duplicate-origin checks. Earlier Jeddah log rows
in the same job belong to mocked tests and are NOT live coverage evidence.
The exact Roshn subject probe encountered `ImageSourceError:request_failed` and
returned no accepted assets; network failures cannot establish catalog absence.
A broader Jeddah probe did recover four public-domain assets from Commons, but
their metadata includes historical offices/processing centers, not verified
Roshn waterfront imagery. Broad city matches do not qualify the narrower story.
No additional paid generation
was run, no image threshold was lowered, and no manual artwork was republished.

Remaining gate: demonstrate at least three distinct relevant publishable images
for an eligible current topic, then run one bounded end-to-end shadow trial on
the updated engine under the shared $3/day cap. Both daily and local must qualify
on the current engine before claiming autonomous production readiness. The
renderer and exact approved-design delivery bytes are unchanged.
