# Final Visual Repair Convergence Design

## Goal

Make the existing bounded visual-repair system converge efficiently without weakening any correctness gate. Every unresolved story should either make safe runtime-visible progress or appear in a deterministic full-board curation output with enough evidence to continue manually.

## Current baseline

- Authoritative runtime PASS count: 25/123.
- `story_runtime.coverage()` remains the sole PASS authority.
- PASS still requires exactly 4 relevant usable local photos and 1 verified relevant local logo.
- Only DIRECT and STRONG_CONTEXT photo verdicts count.
- No guessed logos, no weakened identity checks, no provenance/license bypasses, and no cached acceptance.
- Per-story and per-source latency bounds remain unchanged.
- PR #22 introduced durable advisory failure history and controller-owned full-board curation output.

## Scope

This final change consolidates only the remaining convergence mechanics:

1. Isolate and sanitize durable advisory history.
2. Prioritize near-PASS work deterministically while preserving rotation.
3. Route logo-only stories directly through logo repair without photo discovery.
4. Apply typed story-aware source ordering to photo discovery.
5. Enrich controller-owned curation output with deterministic history and source guidance.

It does not introduce a new logo resolver, new external dependencies, weaker reviewer criteria, new PASS rules, or a new publishing path.

## Durable advisory history

`state/bulk_visual_failure_history.json` is the only persistent failure-memory system.

The history remains advisory and may only suppress work already proven deterministic or a query-set that completed normally with zero eligible candidates. It must never register an asset, create approval, modify runtime coverage, or cause PASS.

Before any production use, history is sanitized against the authoritative story catalogue. Records whose `story` is not one of the real catalogue story strings are dropped. This removes test-fixture entries such as `NVIDIA story` while retaining legitimate production history.

Tests must never write the production history path. Every test that records or saves history must inject a temporary history path or patch the history path at the API boundary. A regression test must prove the repository history file is byte-identical before and after the bulk visual unit suite's history-sensitive operations.

Transient diagnostics remain retryable and never complete a query-set: source rate limiting, source unavailable/network failures, source discovery budget exhaustion, discovery identity skips, and discovery entity-conflict skips.

Accepted candidates are never persisted as approvals.

## Queue convergence

The controller queue prioritizes unresolved stories by runtime deficit band:

1. logo only;
2. one photo;
3. one photo plus logo;
4. all larger deficits.

Ordering inside each band remains deterministic and cursor rotation occurs only within equivalent priority bands so a hard alphabetical prefix cannot permanently starve peers.

Logo-only rows must never invoke photo discovery. The existing process already repairs logo before photo for mixed rows; this design makes the queue intent explicit and adds integration coverage that a zero-photo-deficit story cannot spend photo-source budget.

## Typed source strategy

Photo discovery ordering is selected from already-declared story metadata and explicit story context only. No identity relationship is invented from model output or image pixels.

Preferred bounded ordering:

- Saudi/Gulf company with verified domain: first-party, Commons, LOC, Openverse.
- Person: Commons, LOC, verified first-party when available, Openverse.
- Company: verified first-party, Commons, Openverse, LOC.
- Historical/place subject: Commons, LOC, Openverse, verified first-party.
- Product/invention: Commons, verified first-party, LOC, Openverse.
- Fallback: Commons, LOC, Openverse, verified first-party.

All existing per-source request limits, active-time budgets, retry limits, identity prefilters, same-name conflict handling, download validation, duplicate checks, reviewer rules, provenance requirements, and registration invariants remain unchanged.

## Curation output

The controller emits one full-board artifact at `out/bulk-visual-repair/curation-required.json` after a bounded run using the complete authoritative final board.

Every unresolved story entry contains:

- story string;
- exact remaining photo and logo deficit;
- typed required identity and explicit context when available;
- missing beat keys;
- deterministic completed query-set/source pairs from durable history;
- bounded deterministic rejected source IDs and reasons when present;
- relevant constraints: local usable media, traceable provenance, compatible license, exact identity, DIRECT/STRONG_CONTEXT, no duplicate, verified logo identity;
- a recommended next source class derived from the typed strategy or verified-logo path.

The file is informational only. Reading it cannot affect runtime coverage or PASS.

## Cleanup and compatibility

The stale PR #21 history implementation (`tools/bulk_visual_history.py`) is not imported or revived. PR #22's `tools/bulk_visual_failure_history.py` remains the durable history implementation.

No existing accepted visual asset is removed or reclassified by this change. The current 25-PASS baseline remains valid unless an existing independent runtime test identifies a regression.

## Testing and acceptance

The final PR must keep all existing Tesla, McDonald, Wikimedia, reviewer, duplicate, provenance, registration, runtime relevance, controller rollback, and source-budget regressions green.

New tests must prove:

- fake/non-catalogue story records are removed while real history survives;
- production history is not mutated by tests;
- ACCEPTED remains non-durable;
- transient failures remain retryable;
- deterministic candidate rejections survive and suppress the same source ID;
- completed query fingerprints remain fingerprint-specific;
- logo-only rows skip photo discovery;
- near-PASS priority and within-band rotation are deterministic;
- typed source ordering matches the declared subject type/context;
- curation contains the full unresolved board and bounded history evidence;
- curation/history cannot modify runtime PASS.

No live bulk-repair workflow is run during implementation. After the final PR is reviewed, merged, and green, exactly one bounded production run is used for validation.
