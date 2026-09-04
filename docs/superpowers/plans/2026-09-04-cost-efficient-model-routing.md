# Cost-Efficient Model Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop paid production workflows from running on Git pushes and reduce model spend while preserving Arabic Snapchat editorial quality.

**Architecture:** GitHub Actions becomes the execution firewall: production bots accept schedule, repository-dispatch, and deliberate manual events, but never `push`. Existing model environment variables provide conservative tier routing—Sonnet for audience-facing editorial work and Haiku for structured selection, classification, and vision—while tighter response and dollar ceilings bound failures and retries.

**Tech Stack:** GitHub Actions YAML, Python 3.12, `unittest`, Anthropic Messages API, existing JSONL usage ledger.

**Spec:** `docs/superpowers/specs/2026-09-04-cost-efficient-model-routing-design.md`

## Global Constraints

- Telegram review-only delivery remains fail-closed; paid workflow changes must not enable direct Snapchat publishing.
- Scheduled, `repository_dispatch`, and deliberate `workflow_dispatch` execution must remain available.
- Recovery inputs must not require a commit to `scheduler/triggers/`.
- Sonnet remains the default for audience-facing Arabic editorial work; Haiku remains the default for structured routine decisions.
- No provider switch is deployed without a manual comparison using real project output.

---

### Task 1: Paid Workflow Trigger Firewall

**Files:**
- Create: `tests/test_paid_workflow_policy.py`
- Modify: `.github/workflows/daily.yml`
- Modify: `.github/workflows/topic.yml`
- Modify: `.github/workflows/breaking.yml`
- Modify: `.github/workflows/story.yml`

**Interfaces:**
- Consumes: existing schedule gates and `workflow_dispatch` inputs.
- Produces: paid workflows with no `push` trigger and a News recovery input delivered as `NEWS_RECOVERY_STORY_B64`.

- [ ] **Step 1: Write the failing trigger-policy tests**

```python
import unittest
from pathlib import Path


PAID = ("daily", "topic", "breaking", "story")


def trigger_block(name):
    text = Path(f".github/workflows/{name}.yml").read_text(encoding="utf-8")
    return text.split("on:\n", 1)[1].split("\npermissions:", 1)[0]


class PaidWorkflowPolicyTests(unittest.TestCase):
    def test_paid_workflows_never_run_on_push(self):
        for name in PAID:
            with self.subTest(name=name):
                self.assertNotIn("\n  push:", trigger_block(name))

    def test_paid_workflows_keep_intentional_entrypoints(self):
        for name in PAID:
            with self.subTest(name=name):
                block = trigger_block(name)
                self.assertIn("\n  schedule:", block)
                self.assertIn("\n  workflow_dispatch:", block)

    def test_news_recovery_uses_dispatch_or_manual_input(self):
        text = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")
        self.assertIn("recovery_story:", text)
        self.assertIn("github.event.client_payload.story_b64", text)
        self.assertNotIn("github.event_name == 'push'", text)
```

- [ ] **Step 2: Run the policy test and confirm RED**

Run: `python -m unittest -v tests.test_paid_workflow_policy`

Expected: FAIL because all four workflows currently declare `push`, and News recovery reads a pushed trigger file.

- [ ] **Step 3: Remove paid push entrypoints and preserve explicit recovery**

Delete each top-level `push` block from the four workflow files. In `daily.yml`, add this manual input:

```yaml
      recovery_story:
        description: "Optional exact story for a deliberate recovery run"
        type: string
        required: false
```

Replace the push-only recovery step with:

```yaml
      - name: Load exact News recovery story
        if: ${{ env.RUN_SCHEDULED_BOT != '0' }}
        env:
          DISPATCH_STORY_B64: ${{ github.event.client_payload.story_b64 || '' }}
          MANUAL_RECOVERY_STORY: ${{ inputs.recovery_story || '' }}
        run: |
          if [ -n "$DISPATCH_STORY_B64" ]; then
            echo "NEWS_RECOVERY_STORY_B64=$DISPATCH_STORY_B64" >> "$GITHUB_ENV"
          elif [ -n "$MANUAL_RECOVERY_STORY" ]; then
            encoded="$(printf '%s' "$MANUAL_RECOVERY_STORY" | base64 -w0)"
            echo "NEWS_RECOVERY_STORY_B64=$encoded" >> "$GITHUB_ENV"
          fi
```

Add `repository_dispatch: types: [breaking-recovery]` to `breaking.yml`, and resolve its confirmed event from `github.event.client_payload.confirmed_event` or the existing manual input.

- [ ] **Step 4: Run the policy and schedule-gate tests**

Run: `python -m unittest -v tests.test_paid_workflow_policy tests.test_shared_schedule_gate tests.test_story_workflow_choice`

Expected: PASS.

- [ ] **Step 5: Commit the firewall**

```bash
git add tests/test_paid_workflow_policy.py .github/workflows/daily.yml .github/workflows/topic.yml .github/workflows/breaking.yml .github/workflows/story.yml
git commit -m "fix: block paid workflows on repository pushes"
```

### Task 2: Conservative Cost-Quality Routing

**Files:**
- Modify: `tests/test_model_usage_workflows.py`
- Modify: `.github/workflows/daily.yml`
- Modify: `.github/workflows/topic.yml`
- Modify: `.github/workflows/breaking.yml`
- Modify: `.github/workflows/story.yml`
- Modify: `.github/workflows/batch-review.yml`
- Modify on `repair/all-story-visuals-2026-08-29`: `story_bot.py`
- Modify on `repair/all-story-visuals-2026-08-29`: `story_cost_guard.py`
- Test on repair branch: `tests/test_story_cost_guard.py`

**Interfaces:**
- Consumes: existing model environment variables and JSONL cost guard.
- Produces: Sonnet Story editorial defaults, Haiku routine-task defaults, and tighter per-run ceilings.

- [ ] **Step 1: Update workflow assertions first**

Add assertions that production workflows contain:

```python
self.assertIn('STORY_MODEL: "claude-sonnet-5"', story)
self.assertIn('STORY_MODEL_INPUT_USD_PER_M: "2"', story)
self.assertIn('STORY_MODEL_OUTPUT_USD_PER_M: "10"', story)
self.assertNotIn('STORY_MODEL: "claude-opus-5"', story)
self.assertIn('TOPIC_MAX_PAID_RESPONSES: "2"', topic)
self.assertIn('MODEL_MAX_USD_PER_RUN: "0.5"', daily)
self.assertIn('MODEL_MAX_USD_PER_RUN: "1.5"', topic)
self.assertIn('MODEL_MAX_USD_PER_RUN: "0.15"', breaking)
```

- [ ] **Step 2: Run the workflow assertions and confirm RED**

Run: `python -m unittest -v tests.test_model_usage_workflows`

Expected: FAIL on the old Opus prices, three Topic responses, and broad dollar ceilings.

- [ ] **Step 3: Apply the routing and ceilings**

Use these workflow values:

| Workflow | Editorial model | Dollar ceiling | Editorial/research responses | Vision responses |
|---|---|---:|---:|---:|
| News | Sonnet 5 | $0.50 | 2 | 20 |
| Topic | Sonnet 5 | $1.50 | 2 | 20 |
| Breaking | Haiku 4.5 | $0.15 | classifier 1, editorial 2 | 12 |
| Story | Sonnet 5 | existing one-per-revision guard | 1 | 24 |
| Batch Story | Sonnet 5 | $2.00 | maximum 3 stories | 24 |

Change Story pricing to $2 input / $10 output per million tokens. On the repair branch, change `STORY_MODEL`'s fallback from `claude-opus-5` to `claude-sonnet-5` and update tests that assert the default/pricing behavior.

- [ ] **Step 4: Run main and Story routing tests**

Main run: `python -m unittest -v tests.test_model_usage_workflows tests.test_model_usage tests.test_model_usage_integration`

Repair branch run: `python -m unittest -v tests.test_story_cost_guard tests.test_story_editorial_runtime tests.test_story_cost_report`

Expected: PASS.

- [ ] **Step 5: Commit each branch independently**

```bash
git add tests/test_model_usage_workflows.py .github/workflows/daily.yml .github/workflows/topic.yml .github/workflows/breaking.yml .github/workflows/story.yml .github/workflows/batch-review.yml
git commit -m "feat: route paid tasks by quality and cost"
```

On the repair branch:

```bash
git add story_bot.py story_cost_guard.py tests/test_story_cost_guard.py
git commit -m "feat: default Story editorial work to Sonnet"
```

### Task 3: Provider-Neutral Manual Benchmark Contract

**Files:**
- Create: `model_quality_benchmark.py`
- Create: `tests/test_model_quality_benchmark.py`
- Create: `.github/workflows/model-quality-benchmark.yml`

**Interfaces:**
- Consumes: frozen JSON candidate results containing `provider`, `model`, `task`, `estimated_usd`, `latency_ms`, `validation_passed`, and rubric scores.
- Produces: ranked JSON and Markdown results; the workflow is manual-only and has no publishing credentials.

- [ ] **Step 1: Write failing ranking tests**

```python
def test_cheaper_candidate_only_wins_when_quality_is_not_lower(self):
    baseline = candidate("claude", "sonnet", cost=0.20, quality=90)
    cheap_low = candidate("other", "fast", cost=0.02, quality=89)
    cheap_equal = candidate("other", "balanced", cost=0.05, quality=90)
    ranked = rank_candidates([baseline, cheap_low, cheap_equal], baseline=baseline)
    self.assertEqual(ranked[0]["model"], "balanced")
    self.assertFalse(next(x for x in ranked if x["model"] == "fast")["eligible"])
```

- [ ] **Step 2: Run the benchmark tests and confirm RED**

Run: `python -m unittest -v tests.test_model_quality_benchmark`

Expected: ERROR because `model_quality_benchmark` does not exist.

- [ ] **Step 3: Implement deterministic ranking**

Implement `rank_candidates(candidates, baseline)` so a candidate is eligible only when `validation_passed` is true and its weighted quality is greater than or equal to the baseline. Sort eligible candidates by estimated cost, then latency, then descending quality. The CLI reads JSON, writes ranked JSON, and prints Markdown without calling a model.

- [ ] **Step 4: Add a manual-only workflow**

The workflow must declare only `workflow_dispatch`, accept a checked-in or uploaded frozen result path, run the deterministic ranker, and upload the report. It must not receive Anthropic, OpenAI, Gemini, Telegram, Snapchat, or image-generation secrets.

- [ ] **Step 5: Verify and commit the benchmark contract**

Run: `python -m unittest -v tests.test_model_quality_benchmark tests.test_paid_workflow_policy`

```bash
git add model_quality_benchmark.py tests/test_model_quality_benchmark.py .github/workflows/model-quality-benchmark.yml
git commit -m "feat: add provider-neutral quality cost benchmark"
```

### Task 4: Full Verification and Deployment

**Files:**
- Verify all changed files on both branches.

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: deployed main and Story repair refs with green CI and no paid push-triggered runs.

- [ ] **Step 1: Run the complete main suite**

Run: `python -m unittest discover -s tests`

Expected: PASS.

- [ ] **Step 2: Validate syntax and workflow configuration**

Run: `python -m py_compile model_usage.py model_quality_benchmark.py news_bot.py topic_bot.py topic_snapchat.py breaking_watch.py breaking_news_runner.py story_bot.py`

Run: `python -c "import yaml, pathlib; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]"`

Run: `git diff --check`

Expected: all commands exit 0.

- [ ] **Step 3: Run the complete affected Story suite**

Run on the repair branch: `python -m unittest -v tests.test_story_cost_guard tests.test_story_editorial_runtime tests.test_story_cost_report tests.test_story_aux_usage_integration tests.test_story_workflow_choices tests.test_story_workflow_choice`

Expected: PASS.

- [ ] **Step 4: Rebase both branches and repeat affected verification**

Fetch each remote branch, rebase without force, resolve only verified overlaps, and rerun the affected tests and YAML parsing.

- [ ] **Step 5: Deploy and inspect Actions**

Push `main` and `repair/all-story-visuals-2026-08-29` without force. Confirm the deployed commits are branch ancestors, all triggered CI completes successfully, and none of `News brief to Snapchat`, `Topic brief to Snapchat`, `Daily Story review / manual Snapchat`, or `Breaking news watch` starts because of the deployment push.
