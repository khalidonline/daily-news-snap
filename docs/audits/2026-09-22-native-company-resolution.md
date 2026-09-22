# Native company resolution recovery

The Ceer shadow probe (Actions run 35703612448) passed timing and then held at
`unresolved_editorial_subject`. The editor supplied `Ceer (automotive company)`;
English search returned `Ceer Motors`, which did not satisfy exact-name guards.
Its source-bound Arabic mention was `«سير»`.

Live read-only checks found that `Ceer` redirects to Council of European Energy
Regulators. Stripping a qualifier and trusting that redirect would select the wrong
entity. Arabic `سير` is a disambiguation page; bounded title search includes
`سير (شركة)` (Wikipedia page 8974233). Its introduction matches the source's
Saudi electric-car context. The exact-base resolver selected this page uniquely.

The fallback now removes presentation quotes only after validating the original
mention against the candidate's source. It uses bounded Arabic retrieval and the
existing exact-base contextual resolver. Arabic function words do not count as
context evidence. Conflicting matches remain held. The verified media profile
includes the canonical Arabic company title and its retrieved redirect name.

Regression coverage includes quoted mentions, ambiguous matches, generic Arabic
function words, the actual Ceer title and media-profile handoff, and existing
unrelated-name and native-binding rejections. A replay of the previously retrieved
48-image official catalog confirmed subject metadata matching under `سير (شركة)`.
No model/API generation was used for this repair. This verifies subject recovery
and media lookup, not a completed editorial package or automatic publication.
