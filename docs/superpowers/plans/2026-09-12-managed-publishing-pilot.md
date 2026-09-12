# Managed Publishing Pilot Implementation Plan

> For agentic workers: execute task by task using superpowers:subagent-driven-development. This is the first independently testable stage of the approved migration.

**Goal:** Make supplier access, event-package quality, and recovery behavior measurable before connecting a new production scheduler.

**Architecture:** An isolated `publishing_v2` package separates provider clients, evidence-based evaluation, and durable delivery state. It has no imports from production bots and no Snapchat publishing path. SQLite provides a real persistent store for recovery tests; it is explicitly a local reference implementation, not Cloud Run storage. Cloud Run/Workflows with Firestore remains the deployment target.

**Tech Stack:** Python 3.12 standard library, unittest, GitHub Actions for tests and a manual evaluation workflow. No cloud infrastructure is provisioned in this stage.

**Spec:** docs/superpowers/specs/2026-09-12-event-led-editorial-strategy.md, amended by the owner's approval of managed operations and relaxing the old $3 design constraint.

## Global Constraints

- News is an event trigger; outputs are Info, Topic, and a six-frame real Story.
- A theme expires at the start of its third Saudi calendar day. Retries cannot extend it.
- Preserve existing production schedules, source files, and review-only publishing while the replacement is being evaluated.
- Benchmarks are historical evidence replays, never current news. Synthetic recovery tests must be labelled synthetic.
- Missing provider access is reported as missing, never a pass. Provider discovery does not establish licensed image-download entitlement.
- No secret values, request headers, raw authentication errors, or signed URLs in reports.
- No paid calls by default. The manual model comparison has a finite $10 per-invocation ceiling, no server-side tools, and no automatic retry of an ambiguous paid request. This ceiling is an experiment bound, not a new production budget.
- The existing production $3 guard is not removed or bypassed. New evaluation code has a separate explicit spend ledger.
- A production rollout requires provider access, negotiated image rights, a cloud project, an operations owner, and a successful 3-day Telegram trial. Missing access does not prevent building or testing offline.

## Task 1: Provider clients and access checks

Files: create `publishing_v2/__init__.py`, `publishing_v2/providers.py`, `tests/test_v2_providers.py`.

Interfaces:
- `check_access(provider: str, env: Mapping[str, str], transport=None) -> dict` returns provider, status, and safe detail. Names: openai, anthropic, getty, reuters, gcp. Status: available, missing_credentials, unavailable, setup_required. Models: gpt-6-astra, claude-sonnet-5.
- `generate(provider: str, prompt: str, *, env, transport=None, max_output_tokens=6000) -> dict` returns model, text, usage, response_id, elapsed_ms. It must require a configured credential, restrict the output limit to 1..6000, make exactly one API request, reject incomplete/truncated/refused/malformed responses, and not expose raw exceptions.
- `search_getty(query: str, *, env, transport=None, limit=5) -> list[dict]` performs editorial search only; returns asset id, caption, title, date_created and download availability metadata, without downloading/licensing any asset or exporting URLs with credentials. Cap limit at 10.
- Transport protocol: callable `(method: str, url: str, headers: dict, payload: dict | None) -> dict`. Default transport uses urllib with a 60-second timeout, max response bytes 2MB, HTTPS and no redirects forwarding credentials. Tests inject a recording transport and fake responses; no live calls in unit tests.

Steps:
- [ ] Write tests for absent credentials/no network call; provider-specific authentication and endpoints; malformed responses; 401/429 safe diagnostics; incomplete responses; no raw key leakage; Getty metadata without claiming licensing; output limits before network calls.
- [ ] Run `python -m unittest discover -s tests -p 'test_v2_providers.py' -v` and record failure caused by missing implementation.
- [ ] Implement official OpenAI Responses and Anthropic Messages request/response shapes, model-access GETs, Getty editorial GET search, and explicit setup-required results for Reuters and GCP where end-to-end access has not been established.
- [ ] Run the same tests and commit only task files.

## Task 2: Durable delivery reference and event window

Files: create `publishing_v2/delivery.py`, `tests/test_v2_delivery.py`.

Interfaces:
- `theme_expiry(activated_at: datetime) -> datetime`, `theme_active(activated_at, now) -> bool`; timezone-aware values required. Convert to Asia/Riyadh and expire midnight two calendar days after activation date.
- `DeliveryStore(path)` uses SQLite transactions and exposes `prepare(post_id, event_id, expires_at, frames)`, `deliver(post_id, sender, now)`, and `status(post_id)`. Frames are local paths with stored SHA256 digests, 1 for Info/Topic or exactly 6 for Story through a `format` keyword. IDs and expiry are immutable after preparation; repeated prepare with changed payload must fail.
- sender protocol: `sender(path, key) -> str` returns a nonempty provider receipt. `TemporaryDeliveryError` means definitely not accepted and can be retried later; `AmbiguousDeliveryError` or unexpected failures mean acceptance is unknown and must not be automatically retried.
- Per-frame states: pending, sending, delivered, unknown. Persist sending before external call, persist receipt after acceptance. A process restart encountering sending becomes unknown; concurrent deliver calls must not reclaim an active sending frame. No code automatically resolves unknown. Provide explicit `resolve_unknown(post_id, frame_index, receipt=None, definitely_not_sent=False)`; exactly one proof choice is required.
- Never resend delivered frames; no success until every frame has a receipt. Expired or mutated artifacts must not send. The store does not generate or render any content, and never invokes models.

Steps:
- [ ] Write actual SQLite restart tests: failure on frame 3 preserves receipts for 1 and 2; retry sends 3..6 only; incomplete receipt is unknown; concurrent delivery does not send twice; expired theme blocks first send; expiry during a deck prevents later sends; changed frame bytes block; modified prepared payload is rejected; all six receipts required.
- [ ] Run `python -m unittest discover -s tests -p 'test_v2_delivery.py' -v` before implementation.
- [ ] Implement transaction-backed per-frame delivery and immutable event expiry. Surface pending/unknown/expired rather than claiming failure recovery has completed.
- [ ] Run tests and commit only task files.

## Task 3: Evidence corpus, comparison runner, CI, and operating checklist

Files: create `evaluation/event_packages.json`, `evaluation/failure_cases.json`, `publishing_v2/evaluate.py`, `tests/test_v2_evaluate.py`, `.github/workflows/publishing-v2-tests.yml`, `.github/workflows/publishing-v2-evaluation.yml`, `docs/publishing-v2-pilot.md`.

Interfaces:
- CLI: `python -m publishing_v2.evaluate --mode readiness|offline|models|images --output DIR`. Default mode offline. Models/images require explicit `--allow-paid`; defaults never call external services. Credentials supplied through environment only.
- Readiness writes provider-status JSON with no raw secrets and no claims of deployment.
- Historical evidence corpus has three source-backed event cases with `id`, `event_date`, `replay_date`, `trigger`, `sources` containing id/url/paraphrased facts, and separate Info/Topic/Story objectives. Label every package historical replay.
- Model outputs must supply event identity, separate Info/Topic/Story, source ids for claims, distinct fact ids, and six Story frames. Structural validation is reported separately from editorial/visual approval. No automatic model winner from self-reported quality scores.
- Bounded models comparison runs both named providers over all three cases, saving each response and usage before proceeding. Missing provider makes comparison incomplete. A SQLite reservation ledger persists worst-case budget allocation before each paid call. Maximum text prompt 40KB, maximum output 6000 tokens, no provider search tools. Reserve using UTF-8 byte input bound plus protocol margin and current standard token prices: OpenAI 10/50 and Anthropic 2/10 USD per million input/output tokens. Keep full reservation after unknown/failed calls. Successful settlement uses validated usage; cached inputs may be conservatively charged at full input rate.
- Images comparison searches the three event subjects via Getty when credentials exist and saves metadata candidates for review; it must report entitlement and actual visual review as outstanding. It must not imply downloaded photos were tested.
- CI unit tests are free and run on PRs restricted to new package/test/config paths. Live evaluation is manual-only, separate from production, with no Telegram/Snapchat credentials. Artifacts retained on failure.

Steps:
- [ ] Research three historical event cases using official sources, recording paraphrases rather than invented claims.
- [ ] Write tests proving offline makes no network calls, absent keys do not pass, a second invocation cannot reset the same evaluation ledger, malformed/duplicate/missing-frame outputs fail structural validation, and unreviewed responses never declare a winning provider.
- [ ] Implement runner, docs, and workflows using the above contracts.
- [ ] Run `python -m unittest discover -s tests -p 'test_v2_*.py' -v` and offline evaluation.
- [ ] Review whole diff, publish isolated branch and PR, and verify remote CI if available.

## Completion reporting

Separate built/tested, live supplier evidence, access blockers, and deployment status. Do not claim the paid comparison, licensed photo download evaluation, production migration, staffed support, or 3-day trial is complete without corresponding evidence.
