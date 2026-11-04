# Publication check repair review, 4 November 2026

Base: draft PR #314, `d5a3f2b4009cc9a1086e24008019c03c40a89f52`.
Scope: review four historical executable routes, record only their exact hashes,
and replace an obsolete workflow registration assertion with the actual safety
contract. No application, workflow, request, content, approval, budget or receipt
bytes are changed. This is code review, not publication or factual approval.

## Historical route review

All four files were read in full, with their imports and workflow invocation
paths checked. A second independent static review reached the same assessment.
They are one-off, top-level scripts with local overwrite side effects. None
calls a provider, authorizes a request, or is invoked by a delivery workflow.
They were not imported or executed during this work.

- `approved/us-midterms-20261101/prepare.py` reads local copy/assets, hashes them,
  and writes manifest, archive approval, sources and design-review JSON. Both
  publication approval flags are false. Its archive identity is an older raw
  card digest, not the newer account-bound identity.
- `approved/us-midterms-20261101/render.py` calls the shared fixed renderer,
  writes card/copy/blocks, and writes two local `/tmp` overlay simulations.
- `approved/us-results-20261104/prepare.py` reads the prior package, replaces
  media metadata and resets both approvals false. Its `information_request`
  import calls only the digest-based `identity` helper, not authorization.
  It also reads an absolute historical scratch image path; it is not portable.
- `approved/us-results-20261104/render.py` checks text with `prepare_text`,
  transforms local images, calls the shared renderer, and writes local draft
  and overlay files. It does not generate paid imagery or publish.

Both preparation scripts contain historical visual-review assertions, and the
results script inherits earlier review metadata. These assertions are not proof
for newly rendered bytes. Do not rerun them to fabricate fresh review evidence.
This inventory entry is not a certification that these old scripts can safely
prepare a new package for current delivery. Content claims, rights and current
visual correctness were not revalidated. Published assets remain untouched.

The shared rendering imports read pinned fonts/artwork and enforce geometry.
The publication workflow consumes sealed JSON, never these scripts. The normal
prepared-information delivery path still verifies preparation, authorization,
archive identity, and guarded publishers. No live request is created or changed.

Recorded SHA-256 values:

- Midterms prepare: `85e775c5c7a17f979aa0753b19030a2ddd723b6534590669a06c6371b930f11e`
- Midterms render: `96f2585fdee9cdd71f4060e001d6c25778007d7e2539767688b8c6e140c77e54`
- Results prepare: `7883d82298e03e843f06fdd106958786672c503c0c676f079732e43ea1e47da1`
- Results render: `a89ddc3d48c7ea23b256618c92252d843c7b34e960d3ffd6b48e73602f0e450c`

Only these four absent entries are added. Inventory matching remains exact for
all executable routes; additions, removals and byte changes still fail review.

## Workflow test repair

The old assertion demanded that the request file never exist. A historical
approved request legitimately remains for recovery. Removing it would not be a
safe test fix. Production `resolve_push` already requires the request path to
change in the exact non-forced main push range before validating any package.

The replacement retains existing trigger, serialization and exact-checkout
assertions, and checks the main/repository guard, event set, resolver ordering,
fail-closed resolver step, and delivery package binding to resolver output.
Two real temporary Git histories demonstrate that one- and two-commit unrelated
pushes cannot reuse the retained approved request. Existing tests still cover
explicit multi-commit requests, CLI resolution, forced/wrong-branch/wrong-head
pushes, deleted refs, invalid ranges and modified worktrees.

## Verification

Before changes, focused reproduction: 2 failed, 11 passed. Failures were exactly
the missing four inventory entries and the obsolete request-absence assertion.
After the workflow test change: 13 passed. The route verifier reports 263 exact
executable routes, with no live calls. Further test results follow below.

- Relevant checks plus step 1 (`test_information_text_fit`, information display,
  fixed template, route inventory, request workflow, request contract and
  information delivery): **81 passed**, one existing Pillow deprecation warning.
- Exact publication-contract workflow selection: **73 passed**.
- Replay mutation check: removing only the existing changed-request guard in an
  isolated process made both new regressions fail with `DID NOT RAISE`; no source
  file was modified. Unmodified workflow test selection: **13 passed**.
- Existing public-image-credit suite under the offline workflow's documented
  `FONT_FAMILY=Almarai THEME=light` environment: **5 passed**. This explains why
  the previously observed default-environment legacy render failure is not a
  reason to modify that renderer in this task.
- Full default-environment suite: **1 failed, 1303 passed, 250 subtests passed**,
  two existing Pillow deprecation warnings, 318.95 seconds. The sole failure is
  `tests/test_v2_public_image_credits.py::PublicCreditsTests::test_real_render_to_auto_and_manual_publication`,
  the inherited legacy-renderer configuration mismatch. It passes under the
  workflow environment as verified above. Both requested failures are gone.

Independent final diff review found no blocking defect. Test-created `hero.jpg`,
`hero.jpg.generated` and `out/` are excluded from the commit. This is not a claim
that bare pytest is entirely green, nor permission to merge or publish.
