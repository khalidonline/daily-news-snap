# Snapchat production cost controls — 2026-09-27

Owner-approved scope: choose a worthwhile current Saudi-relevant story for free,
then pay for one package, with repairs inside its original allowance. No price
increase, old schedules, paid trial, publishing or secret extraction is part of
this change.

## Limits

| Work | Model API allowance |
| --- | ---: |
| News/RSS collection, selection, current-trigger verification and preliminary image discovery | $0 |
| Researcher, writer and affected-card text repair combined | $0.75 per package per Saudi day |
| Text review, image check, image assignment and final reviewer combined | $0.50 per package per Saudi day |
| Template rendering and delivery of saved media | No model request |
| All project stages, including rejected attempts and unresolved reservations | $3 per Saudi day |

These are ceilings, not price estimates or mandatory spending. Hosting and the
publishing-service subscription are outside model usage and must not be called
free. ChatGPT usage is also separate from this project's API ledger.

Reservations use the conservative maximum cost BEFORE the provider request;
unused reservation is released only after valid usage is returned. Both package
groups and the daily ceiling are checked in the same optimistic atomic ledger
update. Restarting or concurrently running a job cannot reset that day's group
allowance. A new Saudi day starts a new daily ledger, but does not by itself
authorize another attempt at an interrupted or expired package.

Package identity is the selected candidate ID, including saved replay. Renaming
the stage, omitting the ID, or using `selection:*` cannot authorize a paid request.
All real Agents refuse paid editor/timing/pitch/hooks calls, including direct
callers outside the main coordinator. Existing experimental fake adapters are
not production authority. Existing receipts and the daily limit are preserved.

## Free editorial handoff

The previous three paid shortlists are no longer used by the production agent.
The free editorial/candidate-preparation step supplies ONE brief in
`editorial/selected/YYYY-MM-DD-daily.json` (Saudi date; use `local` for local),
or via `--selection PATH` / the workflow's `selection` input.

Without a brief the run holds with `free_selection_brief_required` before any
model request. It does not silently pick another topic or bypass a review gate.
This is an evidence handoff, not automatic editorial approval or permission to
publish. Free curation must still be performed before scheduling production.

Version 1 schema:

```json
{
  "version": 1,
  "lane": "daily",
  "candidate_id": "ID from current free RSS discovery",
  "choice": {
    "id": "same candidate ID",
    "source_title": "exact discovered title",
    "subjects": ["unambiguous English subject"],
    "subject_evidence": [{"subject": "same English subject", "mention": "exact source name", "quote": "exact title/summary passage containing that name"}],
    "why_saudi": "specific broad audience relevance",
    "why_now": "dated current development",
    "angle": "distinctive fact plus a real background story",
    "share_reason": "what the reader learns and wants to share",
    "research_query": "specific canonical subject"
  },
  "timing": {
    "eligible": true,
    "event_date": "YYYY-MM-DD",
    "timing_basis": "event",
    "event_source_id": "retrieved trigger source ID",
    "event_quote": "exact supporting passage",
    "reason": "why this is a current development, not just a new article timestamp"
  },
  "story": [
    {"point": "beginning", "source_id": "retrieved source ID", "quote": "exact source passage"},
    {"point": "decision or change", "source_id": "retrieved source ID", "quote": "different exact source passage"},
    {"point": "outcome", "source_id": "retrieved source ID", "quote": "different exact source passage"}
  ],
  "image_plan": [
    {"asset_id": "discovered photo ID", "purpose": "info card visual"},
    {"asset_id": "another photo ID", "purpose": "first story stage"},
    {"asset_id": "another photo ID", "purpose": "next story stage"}
  ]
}
```

This example is a schema, NOT a production-ready selection. Quotes and IDs must
come from actual retrieved evidence. Use `Sources.discover`, `Sources.attention`
and `Sources.research` for free retrieval, then `Renderer(None, sources).screen_visuals`
to obtain `candidate.visual_feasibility`; these do not request a model.
Search with purposeful Arabic and English entity/year/history/image terms;
existing subject resolution, official-page routing and image caches are reused.

The coordinator matches the choice to the current discovered pool and existing
owner-rejection/published-memory filters. It verifies event timing, literal story
support and each planned image against the live free image screen BEFORE paid
research. The screen requires downloaded pixels and eligible matching metadata;
it is not a claim that semantic photo suitability or final card quality has
already been approved. Independent paid reviews still verify those.

One failed selected candidate holds the saved attempt, with its reason and
receipts; there is no paid alternative candidate. Text repairs remain confined
to affected cards. Publication stays outside generation/repair handlers and uses
the saved sealed files. Ambiguous delivery stays pending reconciliation, never a
fresh paid generation or duplicate post.

## Entrypoints

Both shadow and live accept one lane only. Workflow defaults are Daily; the
publication workflow cannot send both lanes at once. Live promotion no longer
tries to recover/generate a Local package first. Readiness, expiry, approvals,
quota, reconciliation and anti-duplication protections stay in place. Changing
the engine invalidates previous automated readiness as before.

```sh
python -m publishing_v2.autopilot.runtime --mode shadow --lane daily --selection editorial/selected/YYYY-MM-DD-daily.json
```

Do not run this command until the free handoff is complete and the daily ledger
has sufficient headroom. Offline tests use fake provider transports and no API
credentials; they verify reservation boundaries, concurrency, restart, free
preflight rejection, single-candidate production and workflow routing.

## Verification record

- Production suite: `FONT_FAMILY=Almarai THEME=light PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_v2_*.py' -q`: 466 tests passed.
- New cost controls plus DailyBudgetTests, NativeAgentBudgetTests and GitHubStoreTests: 42 tests passed (overlaps with the production suite).
- Python compilation and both edited workflow YAML files passed validation.
- No paid production or publication was run for verification.
- Full-repository discovery was attempted but did not complete: the execution environment cancelled an external network approval. This is not a full-repository green result.
- A separately run pre-existing static test, `WorkflowBudgetTests.test_paid_workflows_cannot_override_guard_python_path`, fails on the unchanged `reviewer-visual-experiment.yml`: it expects the legacy guard-install step even though that manual experiment has a native shared-budget reservation. That unrelated workflow/test was not weakened or enabled here. The production workflow runs the behavioral shared-budget tests above.
