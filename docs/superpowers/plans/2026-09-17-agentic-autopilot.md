# Agentic autopilot Implementation Plan

**Goal:** Execute daily and local packages through specialist agents and an independent publication gate.
**Architecture:** Bounded coordinator with injected agents, sources, renderer, store and publisher. Production adapters use the existing GitHub budget ledger, template renderers and Bundle receipt journal.
**Tech Stack:** Python 3.12, unittest, Pillow, existing Anthropic/Bundle REST adapters, GitHub Actions.
**Spec:** docs/superpowers/specs/2026-09-17-agentic-autopilot.md

## Global constraints
- $3/day shared ceiling, including retries; unknown spend remains reserved.
- Shadow first; no fake delivery or editorial success claims.
- Evidence-backed Saudi Arabic, relevant images on every card, existing identity.
- Separate reviewer request and hash-bound review; bounded repair and selection.

## Tasks
1. Add tests in `tests/test_v2_autopilot.py` for rejection, changed media,
   source evidence, retry bounds, persisted slots and publishing failure.
   Run `python -m unittest discover -s tests -p test_v2_autopilot.py` before implementation.
2. Implement `publishing_v2/autopilot/policy.py` (evidence and release checks),
   `pipeline.py` (coordinator), `agents.py` (budgeted independent requests),
   `sources.py` (bounded RSS/source and public-domain photo retrieval), and
   `runtime.py` (renderer, persistent state, publisher and CLI).
3. Add adapter tests for prepaid calls, unknown outcomes, unsafe retrieval,
   flexible rendering, and CLI/workflow rollout defaults. Run the full v2 suite.
4. Add `.github/workflows/publishing-v2-autopilot.yml` for shadow execution,
   artifacts and opt-in verified release. Include the shared budget credentials
   and common publisher concurrency group. Document operations and limitations.
5. Independently review the diff, repair findings, run tests and offline pipeline,
   push branch and create PR. Inspect CI before reporting activation readiness.
