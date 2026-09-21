# Image feasibility during topic selection

Owner approved checking images as part of choosing a topic, preserving the
existing design and shared $3/day cap. Generated illustrations are a later
separate step, not enabled by this change.

Inspection found that the pipeline already checks at least three subject images
before paid research/writing and tries the next ranked candidate when they are
unavailable. This change strengthens that existing mechanism rather than adding
a duplicate search or a paid editor call:

- Count different photographs, excluding matching byte hashes or source origins
  across asset IDs and subject searches. Existing rights and relevance filters
  remain in effect.
- Record a candidate as considered first. Record selection only after the image
  check; persist candidate ID, distinct image count and planned asset IDs.
- Clear a previous candidate's feasibility record before considering another.
  Final per-card image selection, review, variety checks and publication gates
  remain mandatory; a feasibility record is not publication approval.

Three regression tests failed before implementation and passed afterwards:
duplicate bytes/origins, shared photos across two subjects, and skipping the
first image-poor candidate before paid research while selecting the second.
Offline evaluation returned offline_ready; the configured full v2 suite passed
282 tests. Independent review found no blockers and passed all three targeted
tests. GitHub CI must pass before merge. No paid trial, publication, renderer change, source
subscription or budget increase is part of this implementation.

This does not manufacture missing image supply or prove full autonomous
readiness. The editor still ranks up to four current strong topics, with no
category preference; availability chooses the first feasible option within that
ranking. Both lanes still require current-engine end-to-end qualification.
