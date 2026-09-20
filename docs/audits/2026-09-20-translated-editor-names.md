# Translated editor names — 20 September 2026

Combined shadow run 35516891749 correctly bound the Luke Littler article and quote, but rejected Arabic presentation using ليتلر because the source name Luke Littler was not copied literally into angle/why_now. That was a false rejection introduced by #227.

The deterministic gate now checks literal names only within the source evidence. Exact source title, verbatim source quote (whitespace-normalized), one evidence record per subject and mention inside that quote remain required. Arabic angle/why_now may translate or shorten a name. Editor instructions distinguish source evidence from presentation. The independent final reviewer explicitly checks that translated names and angles still refer to the source entity using its existing factual/current_attention checks.

This does not claim deterministic semantic validation: an unrelated angle with valid copied source evidence still needs downstream research/reviewer rejection. The old literal check could not prove semantic correctness either. It is deliberately removed rather than replaced with guessed transliteration or fuzzy aliases.

Validation: 6 binding tests, 4 native-source tests and 22 pipeline tests passed (32 total). Translation/short-name regression tests failed before the change. Source swaps, invented quotes and translating the verbatim source mention remain rejected. git diff --check passed. No paid AI calls, full package run or publication.

Next open gate is eligible image supply, identified in the combined trial (Bisht 0, Mohamed Salah 1). Do not rerun paid generation before addressing that supply/attribution decision. Sources cards remain review-only; do not publish them to restore attribution. Autonomous readiness remains unconfirmed.
