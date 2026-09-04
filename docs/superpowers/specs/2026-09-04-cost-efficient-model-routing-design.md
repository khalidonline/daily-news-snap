# Cost-Efficient Model Routing Design

## Goal

Reduce `daily-news-snap` API spend without lowering the quality, relevance, or safety of Arabic Snapchat-ready output.

## Evidence

The 2026-09-04 usage ledger recorded at least $7.16. Push-triggered executions accounted for $6.35 (89%). Story cost $3.23, Topic $1.81, News $1.47, and Breaking $0.64. Opus Story generation cost $2.93 for three editorial responses, while repeated low-cost vision calls added volume and avoidable rerun cost.

## Execution Policy

The paid News, Topic, Story, and Breaking workflows must not declare a GitHub `push` trigger. They may run only from:

- their normal schedule;
- an authorized `repository_dispatch` event; or
- an intentional `workflow_dispatch` manual run.

Recovery data must travel through dispatch payloads or manual inputs rather than commits to files under `scheduler/triggers/`. State and content commits must never start a paid production workflow.

All delivery remains Telegram review-only. `POST_TO_SNAPCHAT=0` stays fail-closed except where an existing manual approval workflow explicitly controls publication.

## Model Routing

Use the least expensive model that reliably performs each job:

| Task | Default tier | Reason |
|---|---|---|
| Story editorial generation | Claude Sonnet 5 | Preserve strong Arabic editorial judgment while replacing Opus 5 at lower token cost. |
| News final editorial copy | Claude Sonnet 5 | This directly affects the audience-facing hook, fact, and relevance. |
| Topic final research and copy | Claude Sonnet 5 | Retain quality for factual synthesis, with paid retries reduced. |
| Selection and classification | Claude Haiku 4.5 | Routine structured decisions do not justify Sonnet or Opus. |
| Image relevance and visual checks | Claude Haiku 4.5 | Existing measurements show low per-call cost and suitable structured output. |

Model names remain environment-configurable. No provider is privileged by architecture. A provider/model may replace a default only after a manual benchmark on real Arabic Snapchat examples demonstrates equal or better quality at lower total cost.

## Cost Controls

- Story editorial generation allows one paid response for a new editorial revision and reuses its existing editorial cache.
- Topic research allows no more than two paid responses per run.
- News editorial allows no more than two paid responses per run.
- Breaking classification allows one paid response per run.
- Vision decisions reuse persisted judgments when the image content and evaluation policy have not changed.
- Every paid workflow retains a hard response ceiling and a per-run dollar ceiling.
- Cost artifacts remain available for review and include workflow, purpose, model, token usage, and estimated cost.

## Provider Benchmark

A manual-only benchmark will compare eligible Claude, OpenAI, and Gemini models using frozen real project inputs. It must score:

- Arabic hook strength and naturalness;
- uniqueness of the selected fact;
- factual faithfulness;
- Saudi Snapchat audience relevance;
- photo relevance decisions;
- validation pass rate;
- latency; and
- total cost per approved output.

The benchmark cannot run on pushes or schedules. It must not publish to Telegram or Snapchat. A model wins only when its quality is at least equal to the current default and its cost is lower.

## Recovery Compatibility

- News receives an explicit recovery-story input or dispatch payload instead of reading a pushed trigger commit.
- Topic continues to accept manual topic/season inputs and repository-dispatch schedule payloads.
- Story continues to accept a custom story, ready-story selection, operation mode, and targeted repair frames.
- Breaking continues to accept an explicitly confirmed event for manual recovery.

## Tests and Acceptance Criteria

1. A regression test fails if any paid workflow declares `push`.
2. Scheduled, repository-dispatch, and manual triggers remain present where currently supported.
3. Recovery inputs reach the same runtime environment variables without a trigger-file push.
4. Story uses Sonnet 5 by default and its price configuration matches the metering table.
5. Routine classification, selection, and vision remain on Haiku 4.5.
6. Existing editorial, relevance, cost-control, scheduling, and review-only tests pass.
7. Workflow YAML parses successfully.
8. GitHub Actions triggered by the deployment are CI-only and make no paid production API calls.

## Rollout

Deploy the trigger firewall and conservative model routing together. Verify CI and inspect GitHub Actions to confirm no paid workflow starts from the deployment push. Continue normal scheduled/manual operation and compare cost per approved output over the following three to seven days before considering a broader provider migration.
