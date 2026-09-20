# Editor/source binding — 20 September 2026

Fresh shadow run 35513642131 paired a Yemen/Taiz article with an angle about Musab Al-Juwayer. Candidate-ID membership alone did not bind the editor's subjects or angle to that source. The attempt stopped at unresolved subject lookup, before images or writing, costing $0.061214.

The editor now returns the exact source title and one subject-evidence record per English subject. Each record contains a verbatim title/summary quote (whitespace normalization only) and the subject's name as written in that quote. That source-language name must also appear in angle or why_now. The pipeline validates this before research or visual planning, rejects invalid candidates individually, and continues the existing bounded ranked list. Candidate rejections preserve ID/title in the audit rather than leaving only the last candidate available.

This is a deterministic evidence-binding gate, not a semantic entailment model: it does not prove the English alias matches the source-language name or every claim in an angle. Encyclopedia resolution, source research and independent content review remain necessary. Reproduced Yemen/football swaps fail even if the editor copies the Yemen title but retains the football quote. No inferred translations or cross-source quote joins are accepted.

Validation: 4 new binding tests, 22 pipeline tests and 9 recovery tests passed (35 focused tests); git diff --check passed. Shared pipeline fixtures now supply the required evidence fields. No paid AI calls, new full trial, archive review, design changes or publication.

Independent review found no blockers.

Next: diagnose the unresolved names from the same fresh trial, preserving source/subject identity, then consider one new shadow trial within the available budget. Do not claim full automated publishing or schedule readiness from this gate alone.
