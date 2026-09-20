# Source-language subject recovery — 20 September 2026

Examined only the three failed candidates in fresh run 35513642131 by retrieving their own journal snapshots (no stories.txt scan).

- Bisht (clothing) already resolved. Al-Ahsa, its second subject, returned Al-Ahsa Governorate but did not establish the requested identity.
- Red Sea Global already resolved. Dr. Sulaiman Al Habib Medical Group returned unrelated King Abdulaziz University and was correctly rejected.
- Musab Al-Juwayer was paired with a Yemen article. Do not repair that invalid source pairing by finding the footballer; #227 now checks source binding.

Implementation: after English subject resolution fails, try the Arabic mention already grounded in that candidate's title/summary. Revalidate the complete editor binding before using it. Require an exact Arabic Wikipedia title or official redirect and non-disambiguation text; do not run broad native search or invent an alias. Preserve the canonical Arabic name for research/images and language-specific encyclopedia IDs and URLs. The diagnostic includes the query that actually resolved. English behavior remains unchanged.

Free source probes verified the Arabic pages الأحساء (746248) and مجموعة الدكتور سليمان الحبيب للخدمات الطبية → مجموعة الحبيب الطبية (1009123). Shortened مجموعة الدكتور سليمان الحبيب did not resolve: precise source names matter. Neither page returned an English langlink in the probe, so this implementation does not manufacture an English equivalence.

20 focused tests passed (4 native lookup, 12 existing resolution, 4 binding); tests exercise source-bound recovery, rejection of mismatched sources, language-scoped IDs, and missing/disambiguation titles without broad search. No paid calls, new package run, or publication.

Limits: no claim that the live editor has produced the new binding fields, that Arabic image queries yield sufficient imagery, or that all names resolve. Existing editorial quality and current-trigger gates remain required. Next checkpoint: a fresh shadow package using source binding plus native recovery, only within the approved budget. Full automated readiness remains unconfirmed.
