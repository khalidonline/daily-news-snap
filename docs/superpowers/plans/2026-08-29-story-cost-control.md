# Cost-Controlled Story-to-Snapchat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve publication quality while limiting each story revision to one paid editorial-model generation and making ordinary reruns/visual repairs editorial-model-free.

**Architecture:** Split Story-to-Snapchat into a versioned editorial-brief layer and a visual assembly/repair layer. A deterministic editorial-quality gate must pass before a brief becomes `EDITORIAL_LOCKED`; locked briefs are cached and reused. A hard call guard, append-only usage ledger, explicit operation modes, frame-only visual repair, and Telegram dedupe prevent repeated paid work and repeated operator review.

**Tech Stack:** Python 3.12, existing Story Bot modules, JSON/JSONL state under `state/`, hashlib, pathlib, unittest, GitHub Actions YAML.

**Spec:** `docs/superpowers/specs/2026-08-29-story-cost-control-design.md` plus `docs/superpowers/specs/2026-08-29-story-cost-control-quality-addendum.md`

## Global Constraints

- `MAX_EDITORIAL_CALLS_PER_REVISION=1` by default.
- `visual_only` permits zero editorial-model calls.
- Ordinary GitHub reruns mean reuse/rerender, never implicit regeneration.
- A brief is cacheable only after the editorial-quality gate passes.
- A failed editorial gate must not automatically buy a second model call.
- Cache corruption/missing cache in `visual_only` fails closed.
- Existing frame relevance, wrong-city/era, dust/haze, runtime relevance, and publishing gates remain at least as strict as today.
- `POST_TO_SNAPCHAT` behavior is unchanged.
- No API keys, auth headers, or private account data may be persisted.
- Telegram should notify only final READY/REVIEW candidates by default, with unchanged-deck dedupe.

---

### Task 1: Versioned editorial brief store

**Files:**
- Create: `story_brief_store.py`
- Test: `tests/test_story_brief_store.py`

**Interfaces:**
- Produces: `revision_key(story: str, prompt: str, model: str, frame_count: int) -> str`
- Produces: `load_locked_brief(story: str, revision: str) -> dict | None`
- Produces: `save_locked_brief(story: str, revision: str, payload: dict) -> Path`
- Produces: `brief_path(story: str, revision: str) -> Path`

- [ ] **Step 1: Write failing tests for stable revision keys and atomic cache round-trip**

```python
class StoryBriefStoreTests(unittest.TestCase):
    def test_revision_key_changes_with_prompt_model_or_frame_count(self):
        base = sbs.revision_key("قصة الرياض", "prompt-a", "claude-opus-5", 6)
        self.assertEqual(base, sbs.revision_key("قصة الرياض", "prompt-a", "claude-opus-5", 6))
        self.assertNotEqual(base, sbs.revision_key("قصة الرياض", "prompt-b", "claude-opus-5", 6))
        self.assertNotEqual(base, sbs.revision_key("قصة الرياض", "prompt-a", "other-model", 6))
        self.assertNotEqual(base, sbs.revision_key("قصة الرياض", "prompt-a", "claude-opus-5", 5))

    def test_locked_brief_round_trip_requires_matching_revision(self):
        payload = {"status": "EDITORIAL_LOCKED", "brief": {"frames": [{"heading": "h"}]}}
        path = sbs.save_locked_brief("قصة الرياض", "abc123", payload)
        self.assertTrue(path.exists())
        self.assertEqual(payload, sbs.load_locked_brief("قصة الرياض", "abc123"))
        self.assertIsNone(sbs.load_locked_brief("قصة الرياض", "different"))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_story_brief_store -v`
Expected: FAIL because `story_brief_store` does not exist.

- [ ] **Step 3: Implement focused store**

```python
BRIEF_SCHEMA_VERSION = "story-brief-v1"
BRIEF_ROOT = Path(os.getenv("STORY_BRIEF_ROOT", "state/story_briefs"))

def _story_id(story: str) -> str:
    return hashlib.sha256(" ".join(story.split()).encode("utf-8")).hexdigest()[:16]

def revision_key(story, prompt, model, frame_count):
    material = json.dumps({
        "schema": BRIEF_SCHEMA_VERSION,
        "story": " ".join(story.split()),
        "prompt": prompt,
        "model": model,
        "frame_count": int(frame_count),
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()

def save_locked_brief(story, revision, payload):
    if payload.get("status") != "EDITORIAL_LOCKED":
        raise ValueError("only EDITORIAL_LOCKED briefs may be cached")
    dest = brief_path(story, revision)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(dest)
    return dest
```

`load_locked_brief` must reject malformed JSON, schema/revision mismatch, or status other than `EDITORIAL_LOCKED` with a dedicated `BriefCacheError` rather than silently returning permission to regenerate.

- [ ] **Step 4: Run tests GREEN**

Run: `python -m unittest tests.test_story_brief_store -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add story_brief_store.py tests/test_story_brief_store.py
git commit -m "feat: add versioned story brief store"
```

---

### Task 2: Deterministic editorial-quality gate before lock

**Files:**
- Create: `story_editorial_quality.py`
- Test: `tests/test_story_editorial_quality.py`

**Interfaces:**
- Produces: `evaluate_brief(brief: dict, expected_frames: int) -> EditorialQualityResult`
- `EditorialQualityResult`: dataclass with `passed: bool`, `status: str`, `reasons: tuple[str, ...]`

- [ ] **Step 1: Write failing quality-gate tests**

```python
def good_brief():
    return {"frames": [
        {"heading": f"مشهد {i}", "text": f"نص واضح ومختلف للقطة رقم {i}",
         "punch": f"خلاصة {i}", "subject_kind": "company",
         "image_keywords": [f"subject {i}"], "image_keywords_ar": [f"موضوع {i}"]}
        for i in range(1, 7)
    ], "sources": ["https://example.com/source"]}

class EditorialQualityTests(unittest.TestCase):
    def test_publication_shaped_brief_passes(self):
        result = seq.evaluate_brief(good_brief(), 6)
        self.assertTrue(result.passed)
        self.assertEqual("EDITORIAL_LOCKED", result.status)

    def test_valid_json_with_duplicate_frames_does_not_lock(self):
        brief = good_brief()
        brief["frames"][4]["heading"] = brief["frames"][3]["heading"]
        brief["frames"][4]["text"] = brief["frames"][3]["text"]
        result = seq.evaluate_brief(brief, 6)
        self.assertFalse(result.passed)
        self.assertEqual("EDITORIAL_REVIEW", result.status)

    def test_missing_sources_fails(self):
        brief = good_brief(); brief["sources"] = []
        self.assertFalse(seq.evaluate_brief(brief, 6).passed)
```

Also cover: wrong frame count, empty required fields, placeholder/model boilerplate, excessive URL/JSON fragments, missing closing payoff, and prohibited comparison/superlative patterns defined by existing house rules.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tests.test_story_editorial_quality -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement local gate without any model/API dependency**

```python
@dataclass(frozen=True)
class EditorialQualityResult:
    passed: bool
    status: str
    reasons: tuple[str, ...]

def evaluate_brief(brief, expected_frames):
    reasons = []
    frames = list((brief or {}).get("frames") or [])
    if len(frames) != expected_frames:
        reasons.append(f"expected {expected_frames} frames, got {len(frames)}")
    # Validate required fields, duplicate normalized headings/bodies,
    # source evidence, opening/middle/closing shape, boilerplate, and house-rule wording.
    return EditorialQualityResult(
        passed=not reasons,
        status="EDITORIAL_LOCKED" if not reasons else "EDITORIAL_REVIEW",
        reasons=tuple(reasons),
    )
```

Use normalized Arabic/Latin token comparison; avoid fuzzy libraries/dependencies. Keep thresholds deterministic and unit-tested.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest tests.test_story_editorial_quality -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add story_editorial_quality.py tests/test_story_editorial_quality.py
git commit -m "feat: gate editorial briefs before locking"
```

---

### Task 3: Hard editorial-call guard and usage ledger

**Files:**
- Create: `story_cost_guard.py`
- Test: `tests/test_story_cost_guard.py`

**Interfaces:**
- Produces: `OperationMode` values `auto`, `visual_only`, `regenerate_editorial`
- Produces: `reserve_editorial_call(story: str, revision: str, mode: str) -> CallReservation`
- Produces: `record_model_result(reservation, *, model, message_id, input_tokens, output_tokens, status) -> None`
- Produces: `record_cache_hit(story, revision, run_id=None, run_attempt=None) -> None`

- [ ] **Step 1: Write failing guard tests**

```python
class CostGuardTests(unittest.TestCase):
    def test_visual_only_forbids_paid_call(self):
        with self.assertRaises(scg.EditorialSpendBlocked):
            scg.reserve_editorial_call("story", "rev", "visual_only")

    def test_second_call_for_same_revision_is_blocked(self):
        first = scg.reserve_editorial_call("story", "rev", "auto")
        scg.record_model_result(first, model="claude-opus-5", message_id="msg_1",
                                input_tokens=100, output_tokens=50, status="success")
        with self.assertRaises(scg.EditorialSpendBlocked):
            scg.reserve_editorial_call("story", "rev", "auto")
```

Add tests proving missing price configuration cannot disable call-count blocking and ledger rows include `GITHUB_RUN_ID`/`GITHUB_RUN_ATTEMPT` when present.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tests.test_story_cost_guard -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement reservation and JSONL ledger**

Use `state/model_usage.jsonl` plus an atomic per-revision reservation marker under `state/model_call_guard/<revision>.json`. Reservation creation must use exclusive create semantics (`open(..., "x")`) so two processes cannot both authorize the same revision.

```python
def reserve_editorial_call(story, revision, mode):
    if mode == "visual_only":
        raise EditorialSpendBlocked("visual_only forbids editorial model calls")
    marker = guard_path(revision)
    try:
        with marker.open("x", encoding="utf-8") as handle:
            json.dump({"story": story, "revision": revision, "reserved_at": utcnow()}, handle)
    except FileExistsError:
        raise EditorialSpendBlocked("editorial call already reserved for revision")
    return CallReservation(...)
```

`regenerate_editorial` must not overwrite the old revision; it must include an explicit regeneration nonce/revision discriminator supplied by the caller so the new paid call is separately auditable.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest tests.test_story_cost_guard -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add story_cost_guard.py tests/test_story_cost_guard.py
git commit -m "feat: guard and audit editorial model calls"
```

---

### Task 4: Wrap Story Bot research with cache + quality + cost guard

**Files:**
- Create: `story_editorial_runtime.py`
- Modify: `story_runtime.py`
- Modify: `story_focus.py` only if needed to expose the final active prompt before research; do not move unrelated logic.
- Test: `tests/test_story_editorial_runtime.py`

**Interfaces:**
- Produces: `configure(story_bot_module) -> module`
- Consumes: `story_brief_store.revision_key/load_locked_brief/save_locked_brief`
- Consumes: `story_editorial_quality.evaluate_brief`
- Consumes: `story_cost_guard.reserve_editorial_call/record_model_result/record_cache_hit`

- [ ] **Step 1: Write failing integration tests with a fake paid research function**

```python
class FakeStoryBot:
    SYSTEM_PROMPT = "prompt"
    STORY_MODEL = "claude-opus-5"
    STORY_FRAMES = 6
    def __init__(self): self.calls = 0
    def research(self, story):
        self.calls += 1
        return good_brief()

def test_first_auto_call_generates_once_then_second_run_hits_cache():
    sb = FakeStoryBot()
    ser.configure(sb)
    first = sb.research("قصة اختبار")
    second = sb.research("قصة اختبار")
    assert sb.calls == 1
    assert first == second
```

Add tests for `visual_only` cache hit = 0 calls; `visual_only` cache miss blocks; quality failure records state but does not cache and does not retry; corrupt cache blocks instead of regenerating.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tests.test_story_editorial_runtime -v`
Expected: FAIL.

- [ ] **Step 3: Implement wrapper order**

Runtime order in `story_runtime.py` must become:

```python
story_focus.configure(sb)
story_editorial_runtime.configure(sb)
city_visual_v3.configure(sb)
```

The wrapper captures the already-Story-Focus-adjusted `research` function as `_research_uncached`, computes the revision key from the final active `SYSTEM_PROMPT`, model, story, and frame count, then:

```python
cached = load_locked_brief(...)
if cached:
    print(f"    EDITORIAL_CACHE_HIT {revision[:12]}")
    record_cache_hit(...)
    return deepcopy(cached["brief"])
if mode == "visual_only":
    raise SystemExit("visual_only requires an EDITORIAL_LOCKED cached brief")
reservation = reserve_editorial_call(...)
brief = _research_uncached(story)
quality = evaluate_brief(brief, sb.STORY_FRAMES)
if not quality.passed:
    record_model_result(..., status="editorial_review")
    raise SystemExit("editorial quality gate failed: " + "; ".join(quality.reasons))
save_locked_brief(..., {"status": "EDITORIAL_LOCKED", "brief": brief, ...})
return deepcopy(brief)
```

Do not add an automatic retry around `_research_uncached`.

- [ ] **Step 4: Run new tests and existing Story Focus/city tests**

Run:
`python -m unittest tests.test_story_editorial_runtime tests.test_story_focus tests.test_city_visual_fallback tests.test_city_visual_decade_match -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add story_editorial_runtime.py story_runtime.py story_focus.py tests/test_story_editorial_runtime.py
git commit -m "feat: reuse quality-locked editorial briefs"
```

---

### Task 5: Explicit GitHub operation modes and safe rerun semantics

**Files:**
- Modify: `.github/workflows/story.yml`
- Test: `tests/test_story_workflow_choice.py`

**Interfaces:**
- Workflow env: `STORY_OPERATION_MODE=auto|visual_only|regenerate_editorial`
- Workflow env: `STORY_REGENERATION_NONCE` only for explicit regeneration
- Workflow env: `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT` already provided by GitHub and consumed directly by Python

- [ ] **Step 1: Add failing workflow-regression assertions**

Tests must parse/read `.github/workflows/story.yml` and assert:

```python
self.assertIn('STORY_OPERATION_MODE:', text)
self.assertIn('visual_only', text)
self.assertIn('regenerate_editorial', text)
self.assertNotIn('STORY_OPERATION_MODE: "regenerate_editorial"', default_path_text)
```

Also assert normal rerun has no expression that converts `github.run_attempt > 1` into regeneration.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tests.test_story_workflow_choice -v`
Expected: FAIL on missing operation-mode controls.

- [ ] **Step 3: Modify workflow dispatch**

Add a choice input:

```yaml
operation_mode:
  description: "Editorial operation mode"
  type: choice
  required: true
  default: auto
  options: [auto, visual_only, regenerate_editorial]
```

Set:

```yaml
STORY_OPERATION_MODE: ${{ inputs.operation_mode || 'auto' }}
STORY_REGENERATION_NONCE: ${{ inputs.operation_mode == 'regenerate_editorial' && github.run_id || '' }}
```

Scheduled runs remain `auto`. Preserve `POST_TO_SNAPCHAT` expression exactly unless a test requires formatting-only changes.

- [ ] **Step 4: Run workflow tests GREEN**

Run: `python -m unittest tests.test_story_workflow_choice -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/story.yml tests/test_story_workflow_choice.py
git commit -m "feat: make story rerun mode explicit"
```

---

### Task 6: Frame-only visual repair state

**Files:**
- Create: `story_visual_state.py`
- Modify: `story_runtime.py`
- Modify: `ready_story_publish.py`
- Test: `tests/test_story_visual_state.py`
- Test: `tests/test_ready_story_publish.py`

**Interfaces:**
- Produces: `load_visual_state(story, revision) -> dict`
- Produces: `save_visual_state(story, revision, state: dict) -> Path`
- Produces: `failed_frame_indices(state: dict) -> tuple[int, ...]`
- Produces: `preserve_approved_frames(previous_state, new_frames, failed_indices) -> list`

- [ ] **Step 1: Write failing tests for preserving untouched slots**

```python
def test_repair_preserves_approved_text_and_visual_slots():
    previous = {"frames": {
        "1": {"status": "PASS", "image": "a.jpg"},
        "2": {"status": "FAIL", "image": None},
        "3": {"status": "PASS", "image": "c.jpg"},
    }}
    self.assertEqual((2,), svs.failed_frame_indices(previous))
```

Add a publishing test proving `visual_only` never calls research when locked brief + visual state exist.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tests.test_story_visual_state tests.test_ready_story_publish -v`
Expected: FAIL.

- [ ] **Step 3: Implement state contract and repair mode**

Persist under `state/story_visuals/<story-id>/<revision>.json`. State each frame with `status`, `image_source`, `asset_hash`, `qa_reasons`, and rendered-frame hash when available.

`visual_only` repair should pass the locked brief directly into the existing image-selection/rendering path and restrict replacement attempts to failed frames. It may rerender the complete six-card deck for layout consistency, but it must preserve approved frame text and approved image source for untouched slots.

Do not add new model calls to this task.

- [ ] **Step 4: Run GREEN plus existing relevance/photo tests**

Run:
`python -m unittest tests.test_story_visual_state tests.test_ready_story_publish tests.test_runtime_relevance tests.test_global_photo_quality -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add story_visual_state.py story_runtime.py ready_story_publish.py tests/test_story_visual_state.py tests/test_ready_story_publish.py
git commit -m "feat: repair only failed story visuals"
```

---

### Task 7: Telegram final-only notification and deck-hash dedupe

**Files:**
- Create: `story_notification_state.py`
- Modify: `ready_story_publish.py`
- Test: `tests/test_story_notification_state.py`
- Test: `tests/test_ready_story_publish.py`

**Interfaces:**
- Produces: `deck_hash(frame_paths: Iterable[Path]) -> str`
- Produces: `should_notify(story, revision, status, deck_hash) -> bool`
- Produces: `record_notification(story, revision, status, deck_hash) -> None`

- [ ] **Step 1: Write failing notification tests**

```python
def test_same_ready_deck_not_sent_twice():
    self.assertTrue(sns.should_notify("story", "rev", "READY", "hash1"))
    sns.record_notification("story", "rev", "READY", "hash1")
    self.assertFalse(sns.should_notify("story", "rev", "READY", "hash1"))
    self.assertTrue(sns.should_notify("story", "rev", "READY", "hash2"))

def test_internal_visual_only_attempt_is_not_notified():
    self.assertFalse(sns.should_notify("story", "rev", "VISUAL_ASSEMBLY", "hash"))
```

- [ ] **Step 2: Run RED**

Run: `python -m unittest tests.test_story_notification_state -v`
Expected: FAIL.

- [ ] **Step 3: Implement notification ledger and publish integration**

Persist `state/story_notifications.jsonl`. In `ready_story_publish.py`, move Telegram album sending behind final status evaluation. Only `READY` and genuine `REVIEW` are eligible; unchanged deck hash is suppressed. GitHub artifact upload remains unaffected.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest tests.test_story_notification_state tests.test_ready_story_publish -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add story_notification_state.py ready_story_publish.py tests/test_story_notification_state.py tests/test_ready_story_publish.py
git commit -m "feat: notify only final story candidates"
```

---

### Task 8: CI coverage, end-to-end cache proof, and 10-story pilot harness

**Files:**
- Modify: `.github/workflows/runtime-relevance-tests.yml`
- Create: `story_cost_report.py`
- Create: `tests/test_story_cost_report.py`
- Modify: `README.md` or `CLAUDE.md` only for the operator commands added here.

**Interfaces:**
- Produces CLI: `python story_cost_report.py --last 10`
- Reads `state/model_usage.jsonl`, story states, and notification state; does not call external APIs.

- [ ] **Step 1: Add new test modules to CI and write failing report test**

Expected CI commands include:

```yaml
- name: Story cost-control regressions
  run: python -m unittest \
       tests.test_story_brief_store \
       tests.test_story_editorial_quality \
       tests.test_story_cost_guard \
       tests.test_story_editorial_runtime \
       tests.test_story_visual_state \
       tests.test_story_notification_state \
       tests.test_story_cost_report -v
```

Report test should feed a temporary JSONL ledger and assert counts for paid calls, cache hits, visual-only runs, and estimated USD where present.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tests.test_story_cost_report -v`
Expected: FAIL because reporter does not exist.

- [ ] **Step 3: Implement local cost/operation report**

Output fields:

```text
stories: 10
paid_editorial_calls: 10
cache_hits: 7
visual_only_runs: 5
estimated_usd: <sum or 'unpriced'>
second_call_blocks: <count>
ready: <count>
review: <count>
blocked: <count>
```

No web/API calls.

- [ ] **Step 4: Run the complete regression suite**

Run the exact commands from `.github/workflows/runtime-relevance-tests.yml`, including all existing relevance, city, global photo-quality, compile, precheck, Bogle, and new cost-control suites.
Expected: all PASS.

- [ ] **Step 5: End-to-end dry proof on one existing locked/test story**

First dry `auto` run: expect either one paid editorial generation for a genuinely uncached revision or a cache hit if already seeded.

Second dry `auto` run on identical story/prompt/model: require log line `EDITORIAL_CACHE_HIT` and verify the usage ledger has no second paid editorial call.

Third dry `visual_only` run: require zero editorial calls and successful render/repair behavior.

All three use `POST_TO_SNAPCHAT=0`.

- [ ] **Step 6: Pilot 10 representative stories**

Select one story from each approved category in the spec. Do not bulk-run the full backlog. Record paid calls/story, cache-hit reruns, first-pass READY, visual repairs, REVIEW rate, and estimated cost.

Pilot acceptance:
- no revision exceeds one default paid editorial call;
- every ordinary rerun of a cached revision uses zero editorial calls;
- visual-only uses zero editorial calls;
- no publication-quality gate is weakened;
- operator receives only final READY/REVIEW candidates.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/runtime-relevance-tests.yml story_cost_report.py tests/test_story_cost_report.py README.md CLAUDE.md
git commit -m "test: verify cost-controlled story operation"
```

---

## Final verification checklist

- [ ] `git status --short` shows only intended changes before final commit.
- [ ] Full CI is green on the exact final SHA.
- [ ] Same-story rerun visibly logs `EDITORIAL_CACHE_HIT`.
- [ ] `state/model_usage.jsonl` contains at most one default paid call per revision.
- [ ] `visual_only` cannot call the editorial model even with a missing/corrupt cache.
- [ ] Editorially weak mocked briefs never become `EDITORIAL_LOCKED`.
- [ ] Existing Riyadh wrong-city/era/haze protections remain green.
- [ ] `POST_TO_SNAPCHAT=0` for all verification runs.
- [ ] Telegram does not resend an unchanged intermediate/READY deck.
- [ ] 10-story pilot metrics are captured before any full-backlog execution.
