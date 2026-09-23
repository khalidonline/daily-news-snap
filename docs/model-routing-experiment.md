# Model routing experiment

## Decision rule

Production model routing stays unchanged until a manual benchmark passes. A cheaper
model is not promoted merely because it costs less.

The workflow is:

1. Reuse frozen real project inputs and the exact production writer instructions.
2. Run the current production writer as the baseline beside lower-cost candidates.
3. Present the outputs as A/B/C without model names for editorial review.
4. Reject any output that fails structural/factual validation.
5. Score the surviving frozen outputs with the existing quality benchmark.
6. A candidate may replace the baseline only if its measured quality is at least
   the baseline. Among qualifying candidates, prefer lower total cost, then lower latency.
7. Benchmark the reviewer role separately after the writer decision; do not assume
   the best writer is also the best reviewer.
8. Change one production role at a time and validate a shadow run before relying on
   the new route.

## First experiment

The first writer comparison uses the three frozen cases already in
evaluation/event_packages.json:

- iPhone 16 / first iPhone
- Riyadh Metro
- Voyager 1

Candidates:

- current baseline: claude-opus-5
- lower-cost Anthropic candidate: claude-sonnet-5
- OpenAI candidate: gpt-5.6-sol

The experiment is manual-only, cannot publish to Telegram or Snapchat, cannot
change autopilot readiness, reserves at most $0.75, and that reservation is made
inside the same shared $3 daily ledger used by production.
Missing credentials produce an unavailable result rather than falling back to a
different model.

## Production cost method

Keep deterministic validation and cached/replayable state before paid generation.
If a later review is blocked by budget, resume the saved review stage rather than
paying the writer again. Do not rerun an already successful paid stage merely to
recover a downstream failure.

Routine roles such as timing, classification and visual checks are benchmarked
separately after the writer/reviewer choice. This avoids changing several quality
variables at once.

## Files

- .github/workflows/model-role-experiment.yml runs the paid blind comparison by
  explicit manual dispatch only.
- model_role_experiment.py records output, token usage, latency and estimated
  per-response cost.
- model-experiment-blind.md is the editorial review surface and hides model names.
- model-experiment-key.json keeps the label-to-model key and measurements.
- .github/workflows/model-quality-benchmark.yml applies the existing frozen
  quality/cost ranking after scores are supplied.
