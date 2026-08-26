# Bulk Visual Repair Runner Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unbounded catalogue fallback scan with a resumable, observable, fail-closed runner that attempts at most 12 stories per invocation, enforces a 150-second per-story budget and a 30-minute job budget, checkpoints every validated improvement immediately, and advances past hard stories across runs.

**Architecture:** Add a focused queue/cursor module and a Python run controller so timeout, rollback, cursor advancement, checkpointing, and status semantics are testable outside YAML. Keep `tools/bulk_visual_repair.py` as the strict single-story repair engine and keep `story_runtime.coverage()` as the only PASS authority; the GitHub workflow becomes a thin bounded wrapper around the new controller.

**Tech Stack:** Python 3.12, `unittest`, `subprocess`, Git CLI, GitHub Actions YAML, existing Pillow/runtime visual tooling.

**Spec:** `docs/superpowers/specs/2026-08-26-bulk-visual-repair-runner-redesign.md`

## Global Constraints

- PASS remains exactly four distinct relevant usable local photos plus one relevant local logo.
- Only `DIRECT` and `STRONG_CONTEXT` photos count; weak/generic, wrong-entity, duplicate, missing, remote, and unreviewed assets remain rejected.
- `story_runtime.coverage()` remains the only PASS/deficit authority.
- Do not guess logos when exact identity cannot be proven.
- Do not modify runtime relevance semantics or approval-ledger semantics.
- Do not merge PR #2 or enable Story publishing.
- Repair writes remain serialized; do not add parallel branch writers.
- Default bounded slice: at most 12 unresolved stories per invocation.
- Per-story hard wall-clock budget: 150 seconds.
- GitHub Actions repair-job hard budget: 30 minutes.
- Stop starting new story probes after approximately 25 minutes so validation/checkpoint/artifact work can finish.
- A timeout with no runtime-visible deficit reduction must restore `images/**` and `stories.txt` to the last committed checkpoint before the next story.
- Exit code 3 remains an invariant failure and must stop immediately without advancing the cursor past the offending story.

---

## File Structure

- Create `tools/bulk_visual_queue.py` — deterministic class-aware queue construction plus persisted cursor load/save/rotation.
- Create `tools/bulk_visual_run.py` — bounded run controller: clean-tree precondition, subprocess lifecycle, timeout, post-attempt runtime comparison, rollback, validation, checkpoint push, summary, and exit semantics.
- Create `state/bulk_visual_repair_cursor.json` — orchestration position only; no approval decisions.
- Create `tests/test_bulk_visual_queue.py` — cursor rotation and class-order regressions.
- Create `tests/test_bulk_visual_run.py` — timeout, rollback, checkpoint, logging, budget, and exit-code regressions.
- Modify `.github/workflows/bulk-visual-repair.yml` — replace the nested batch/full-backlog scan with one bounded controller call and add `timeout-minutes: 30`.
- Modify `tests/test_bulk_visual_workflow.py` — assert the workflow is thin, bounded, and maps expected bounded outcomes to GitHub success.
- Modify `tools/bulk_visual_repair.py` only if the controller needs a stable single-story refresh/result interface; do not move gate logic into the controller.

---

### Task 1: Class-aware queue and persisted cursor

**Files:**
- Create: `tools/bulk_visual_queue.py`
- Create: `state/bulk_visual_repair_cursor.json`
- Create: `tests/test_bulk_visual_queue.py`
- Read: `tools/bulk_visual_board.py`

**Interfaces:**
- Consumes: `CoverageRow` from `tools.bulk_visual_board`.
- Produces:
  - `CURSOR_PATH = Path("state/bulk_visual_repair_cursor.json")`
  - `QUEUE_CLASSES = ("photo-needed", "logo-only")`
  - `queue_class(row: CoverageRow) -> str`
  - `load_cursor(path: str | Path = CURSOR_PATH) -> dict[str, str | None]`
  - `save_cursor(cursor: dict[str, str | None], path: str | Path = CURSOR_PATH) -> Path`
  - `build_run_queue(rows: Iterable[CoverageRow], cursor: Mapping[str, str | None], limit: int = 12) -> list[CoverageRow]`
  - `advance_cursor(cursor: Mapping[str, str | None], row: CoverageRow) -> dict[str, str | None]`

- [ ] **Step 1: Write the RED queue tests**

Create `tests/test_bulk_visual_queue.py` with focused fixtures:

```python
import json
import tempfile
import unittest
from pathlib import Path

from tools.bulk_visual_board import CoverageRow
from tools.bulk_visual_queue import (
    advance_cursor, build_run_queue, load_cursor, queue_class, save_cursor,
)


def row(story, need_photos, need_logo, status="NEEDS"):
    return CoverageRow(story, tuple(), tuple(), need_photos, need_logo, status)


class BulkVisualQueueTests(unittest.TestCase):
    def test_photo_needed_rows_precede_logo_only_rows(self):
        rows = [
            row("Logo A", 0, True),
            row("Photo B", 2, False),
            row("Mixed C", 1, True),
        ]
        queue = build_run_queue(rows, {"photo-needed": None, "logo-only": None}, 12)
        self.assertEqual([item.story for item in queue], ["Mixed C", "Photo B", "Logo A"])
        self.assertEqual(queue_class(queue[0]), "photo-needed")
        self.assertEqual(queue_class(queue[-1]), "logo-only")

    def test_cursor_rotates_past_previous_hard_prefix(self):
        rows = [row("A", 1, False), row("B", 1, False), row("C", 1, False)]
        queue = build_run_queue(rows, {"photo-needed": "B", "logo-only": None}, 3)
        self.assertEqual([item.story for item in queue], ["C", "A", "B"])

    def test_missing_cursor_story_starts_from_deterministic_head(self):
        rows = [row("B", 1, False), row("A", 1, False)]
        queue = build_run_queue(rows, {"photo-needed": "Gone", "logo-only": None}, 2)
        self.assertEqual([item.story for item in queue], ["A", "B"])

    def test_limit_is_hard(self):
        rows = [row(f"Story {n:02d}", 1, False) for n in range(20)]
        self.assertEqual(len(build_run_queue(rows, {"photo-needed": None, "logo-only": None}, 12)), 12)

    def test_cursor_round_trip_and_advance(self):
        cursor = {"photo-needed": None, "logo-only": None}
        cursor = advance_cursor(cursor, row("Hard Photo", 1, False))
        cursor = advance_cursor(cursor, row("Hard Logo", 0, True))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cursor.json"
            save_cursor(cursor, path)
            self.assertEqual(load_cursor(path), {
                "photo-needed": "Hard Photo",
                "logo-only": "Hard Logo",
            })
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], 1)
```

- [ ] **Step 2: Run the queue tests and verify RED**

Run:

```bash
python -m unittest -v tests.test_bulk_visual_queue
```

Expected: import/error failures because `tools.bulk_visual_queue` does not exist yet.

- [ ] **Step 3: Implement the minimal queue/cursor module**

Create `tools/bulk_visual_queue.py` with deterministic ordering and rotation:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

from tools.bulk_visual_board import CoverageRow

CURSOR_PATH = Path("state/bulk_visual_repair_cursor.json")
QUEUE_CLASSES = ("photo-needed", "logo-only")


def queue_class(row: CoverageRow) -> str:
    return "photo-needed" if row.need_photos else "logo-only"


def _sort_key(row: CoverageRow):
    return (
        row.need_photos + int(row.need_logo),
        row.need_photos,
        int(row.need_logo),
        row.story.casefold(),
    )


def _rotate(rows: list[CoverageRow], after_story: str | None) -> list[CoverageRow]:
    if not rows or not after_story:
        return rows
    for index, row in enumerate(rows):
        if row.story == after_story:
            return rows[index + 1:] + rows[:index + 1]
    return rows


def load_cursor(path=CURSOR_PATH):
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        payload = {}
    return {name: payload.get(name) for name in QUEUE_CLASSES}


def save_cursor(cursor, path=CURSOR_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, **{name: cursor.get(name) for name in QUEUE_CLASSES}}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def build_run_queue(rows: Iterable[CoverageRow], cursor: Mapping[str, str | None], limit=12):
    limit = max(0, int(limit))
    classes = {}
    for name in QUEUE_CLASSES:
        members = sorted(
            (row for row in rows if row.status != "PASS" and queue_class(row) == name),
            key=_sort_key,
        )
        classes[name] = _rotate(members, cursor.get(name))
    return (classes["photo-needed"] + classes["logo-only"])[:limit]


def advance_cursor(cursor, row: CoverageRow):
    updated = {name: cursor.get(name) for name in QUEUE_CLASSES}
    updated[queue_class(row)] = row.story
    return updated
```

Create `state/bulk_visual_repair_cursor.json`:

```json
{
  "version": 1,
  "photo-needed": null,
  "logo-only": null
}
```

- [ ] **Step 4: Run the queue tests and the existing board tests**

Run:

```bash
python -m unittest -v tests.test_bulk_visual_queue tests.test_bulk_visual_board
```

Expected: all tests PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add tools/bulk_visual_queue.py tests/test_bulk_visual_queue.py state/bulk_visual_repair_cursor.json
git commit -m "feat: add resumable visual repair queue"
```

---

### Task 2: Single-story probe lifecycle, timeout, and rollback

**Files:**
- Create: `tools/bulk_visual_run.py`
- Create: `tests/test_bulk_visual_run.py`
- Read: `tools/bulk_visual_repair.py`

**Interfaces:**
- Consumes: `build_board`, `CoverageRow`, queue helpers from Task 1, and the existing CLI `tools/bulk_visual_repair.py --story <title> --batch-stories 1 --max-candidates-per-beat <n>`.
- Produces:
  - `ProbeResult` dataclass with `story`, `queue_class`, `before_gap`, `after_gap`, `returncode`, `elapsed_seconds`, `timed_out`, and `result`.
  - `runtime_row(story: str) -> CoverageRow` that reloads Story Bot metadata before calling `build_board([story])`.
  - `visual_worktree_status() -> list[str]`.
  - `restore_visual_worktree() -> None`.
  - `run_story_probe(row: CoverageRow, max_candidates: int, timeout_seconds: int = 150) -> ProbeResult`.

- [ ] **Step 1: Write RED tests for timeout, refresh, and rollback primitives**

Start `tests/test_bulk_visual_run.py` with mocks around process and Git boundaries:

```python
import subprocess
import unittest
from unittest.mock import Mock, patch

from tools.bulk_visual_board import CoverageRow
import tools.bulk_visual_run as runner


def row(story, need_photos, need_logo, status="NEEDS"):
    return CoverageRow(story, tuple(), tuple(), need_photos, need_logo, status)


class BulkVisualRunProbeTests(unittest.TestCase):
    @patch.object(runner.sb, "load_stories")
    @patch.object(runner, "build_board")
    def test_runtime_row_reloads_story_metadata(self, board, load_stories):
        expected = row("Story", 0, False, "PASS")
        board.return_value = [expected]
        self.assertEqual(runner.runtime_row("Story"), expected)
        load_stories.assert_called_once_with()
        board.assert_called_once_with(["Story"])

    @patch.object(runner, "_spawn_story_process")
    @patch.object(runner, "runtime_row")
    def test_timeout_is_labeled_and_post_coverage_is_still_measured(self, runtime_row, spawn):
        proc = Mock()
        proc.wait.side_effect = subprocess.TimeoutExpired("repair", 150)
        proc.poll.return_value = None
        spawn.return_value = proc
        runtime_row.return_value = row("Hard", 1, False)
        result = runner.run_story_probe(row("Hard", 1, False), 12, timeout_seconds=150)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.result, "TIME_BUDGET_EXCEEDED")
        self.assertEqual(result.after_gap, 1)

    @patch.object(runner, "_git")
    def test_restore_visual_worktree_restores_tracked_and_removes_attempt_untracked(self, git):
        runner.restore_visual_worktree()
        self.assertEqual(git.call_args_list[0].args[0], [
            "restore", "--source=HEAD", "--staged", "--worktree", "--", "images", "stories.txt",
        ])
        self.assertEqual(git.call_args_list[1].args[0], ["clean", "-fd", "--", "images"])
```

Add a process-group termination assertion so a timed-out child cannot leave descendants running:

```python
    @patch.object(runner.os, "killpg")
    @patch.object(runner, "_spawn_story_process")
    @patch.object(runner, "runtime_row")
    def test_timeout_terminates_the_story_process_group(self, runtime_row, spawn, killpg):
        proc = Mock(pid=321)
        proc.wait.side_effect = [subprocess.TimeoutExpired("repair", 150), None]
        proc.poll.return_value = None
        spawn.return_value = proc
        runtime_row.return_value = row("Hard", 1, False)
        runner.run_story_probe(row("Hard", 1, False), 12, timeout_seconds=150)
        killpg.assert_called()
```

- [ ] **Step 2: Run the probe tests and verify RED**

Run:

```bash
python -m unittest -v tests.test_bulk_visual_run.BulkVisualRunProbeTests
```

Expected: import/error failures because `tools.bulk_visual_run` does not exist.

- [ ] **Step 3: Implement the probe and rollback primitives**

Create `tools/bulk_visual_run.py` with these concrete rules:

```python
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import story_bot as sb
from tools.bulk_visual_board import CoverageRow, build_board
from tools.bulk_visual_queue import advance_cursor, build_run_queue, load_cursor, save_cursor

OUT_DIR = Path("out/bulk-visual-repair")
VISUAL_PATHS = ("images", "stories.txt")


@dataclass(frozen=True)
class ProbeResult:
    story: str
    queue_class: str
    before_gap: int
    after_gap: int
    returncode: int
    elapsed_seconds: float
    timed_out: bool
    result: str


def gap(row):
    return row.need_photos + int(row.need_logo)


def runtime_row(story):
    sb.load_stories()
    return build_board([story])[0]


def _git(args, *, check=True):
    return subprocess.run(["git", *args], check=check, text=True, capture_output=True)


def visual_worktree_status():
    result = _git(["status", "--porcelain", "--", "images", "stories.txt"])
    return [line for line in result.stdout.splitlines() if line.strip()]


def restore_visual_worktree():
    _git(["restore", "--source=HEAD", "--staged", "--worktree", "--", "images", "stories.txt"])
    _git(["clean", "-fd", "--", "images"])


def _spawn_story_process(story, max_candidates):
    return subprocess.Popen(
        [sys.executable, "tools/bulk_visual_repair.py", "--story", story,
         "--batch-stories", "1", "--max-candidates-per-beat", str(max_candidates)],
        start_new_session=True,
    )
```

Implement timeout handling with `proc.wait(timeout=timeout_seconds)`, `os.killpg(proc.pid, signal.SIGTERM)`, a five-second grace wait, then `SIGKILL` if still alive. Always call `runtime_row(story)` after the child finishes or is killed. Label results exactly:

- rc `3` -> `INVARIANT`
- timeout -> `TIME_BUDGET_EXCEEDED`
- deficit reduction > 0 -> `SAFE_PROGRESS`
- rc in `{0, 2, 10}` and no reduction -> `NO_PROGRESS`
- any other rc -> `SYSTEM_ERROR`

- [ ] **Step 4: Run the probe tests**

Run:

```bash
python -m unittest -v tests.test_bulk_visual_run.BulkVisualRunProbeTests
```

Expected: all probe tests PASS.

- [ ] **Step 5: Add and run the clean-start guard test**

Add:

```python
    @patch.object(runner, "visual_worktree_status", return_value=["?? images/leftover.jpg"])
    def test_runner_refuses_preexisting_visual_dirt(self, status):
        with self.assertRaisesRegex(RuntimeError, "visual worktree must be clean"):
            runner.assert_clean_visual_worktree()
```

Implement:

```python
def assert_clean_visual_worktree():
    dirty = visual_worktree_status()
    if dirty:
        raise RuntimeError("visual worktree must be clean before bounded repair: " + "; ".join(dirty))
```

Run:

```bash
python -m unittest -v tests.test_bulk_visual_run.BulkVisualRunProbeTests
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add tools/bulk_visual_run.py tests/test_bulk_visual_run.py
git commit -m "feat: add bounded story repair probe"
```

---

### Task 3: Bounded controller, immediate checkpoints, and safe cursor advancement

**Files:**
- Modify: `tools/bulk_visual_run.py`
- Modify: `tests/test_bulk_visual_run.py`
- Read: `tools/build_runtime_review.py`

**Interfaces:**
- Consumes: Task 1 queue/cursor functions and Task 2 `ProbeResult`/probe/rollback primitives.
- Produces:
  - `validate_checkpoint() -> None`
  - `commit_checkpoint(cursor, message: str, visual_progress: bool) -> None`
  - `RunSummary` dataclass with start/final PASS, attempted, timed_out, progress_count, no_progress_count, last attempted story per class, outcome.
  - `run_bounded(max_stories=12, max_candidates=12, story_timeout_seconds=150, soft_deadline_seconds=1500) -> int`
  - `write_summary(summary, path=OUT_DIR / "run-summary.json") -> Path`

- [ ] **Step 1: Write RED controller tests**

Extend `tests/test_bulk_visual_run.py`:

```python
class BulkVisualRunControllerTests(unittest.TestCase):
    @patch.object(runner, "build_run_queue")
    @patch.object(runner, "build_board")
    @patch.object(runner, "assert_clean_visual_worktree")
    @patch.object(runner, "run_story_probe")
    @patch.object(runner, "restore_visual_worktree")
    @patch.object(runner, "commit_checkpoint")
    def test_no_progress_slice_is_bounded_and_pushes_cursor_only(
        self, checkpoint, restore, probe, clean, board, queue
    ):
        items = [row(f"Story {n}", 1, False) for n in range(20)]
        board.side_effect = [items, items]
        queue.return_value = items[:12]
        probe.side_effect = [runner.ProbeResult(
            item.story, "photo-needed", 1, 1, 2, 0.1, False, "NO_PROGRESS"
        ) for item in items[:12]]
        rc = runner.run_bounded(max_stories=12, soft_deadline_seconds=1500)
        self.assertEqual(probe.call_count, 12)
        self.assertEqual(restore.call_count, 12)
        checkpoint.assert_called_once()
        self.assertFalse(checkpoint.call_args.kwargs["visual_progress"])
        self.assertEqual(rc, 2)

    @patch.object(runner, "run_story_probe")
    @patch.object(runner, "validate_checkpoint")
    @patch.object(runner, "commit_checkpoint")
    def test_safe_progress_is_validated_and_pushed_before_next_story(self, checkpoint, validate, probe):
        first = row("First", 1, False)
        second = row("Second", 1, False)
        probe.side_effect = [
            runner.ProbeResult("First", "photo-needed", 1, 0, 10, 1.0, False, "SAFE_PROGRESS"),
            runner.ProbeResult("Second", "photo-needed", 1, 1, 2, 1.0, False, "NO_PROGRESS"),
        ]
        with patch.object(runner, "_initial_and_queue", return_value=([first, second], [first, second], {"photo-needed": None, "logo-only": None})), \
             patch.object(runner, "_final_board", return_value=[first, second]), \
             patch.object(runner, "restore_visual_worktree"):
            runner.run_bounded(max_stories=2)
        self.assertGreaterEqual(checkpoint.call_count, 1)
        self.assertEqual(checkpoint.call_args_list[0].kwargs["visual_progress"], True)
        validate.assert_called()

    @patch.object(runner, "run_story_probe")
    @patch.object(runner, "commit_checkpoint")
    def test_invariant_aborts_without_checkpointing_offending_cursor(self, checkpoint, probe):
        item = row("Bad", 1, False)
        probe.return_value = runner.ProbeResult(
            "Bad", "photo-needed", 1, 1, 3, 1.0, False, "INVARIANT"
        )
        with patch.object(runner, "_initial_and_queue", return_value=([item], [item], {"photo-needed": None, "logo-only": None})), \
             patch.object(runner, "_final_board", return_value=[item]):
            self.assertEqual(runner.run_bounded(max_stories=1), 3)
        checkpoint.assert_not_called()

    @patch.object(runner, "time")
    def test_soft_deadline_stops_starting_new_stories(self, fake_time):
        fake_time.monotonic.side_effect = [0, 1490, 1510]
        item = row("Late", 1, False)
        with patch.object(runner, "_initial_and_queue", return_value=([item], [item], {"photo-needed": None, "logo-only": None})), \
             patch.object(runner, "run_story_probe") as probe, \
             patch.object(runner, "commit_checkpoint"), \
             patch.object(runner, "_final_board", return_value=[item]):
            runner.run_bounded(max_stories=1, soft_deadline_seconds=1500)
        probe.assert_not_called()
```

Also add a timeout-with-progress test and timeout-without-progress rollback test:

```python
    def test_timeout_with_runtime_progress_uses_checkpoint_path(self):
        result = runner.ProbeResult("Partial", "photo-needed", 2, 1, 124, 150.0, True, "TIME_BUDGET_EXCEEDED")
        self.assertTrue(runner.has_safe_progress(result))

    def test_timeout_without_runtime_progress_requires_rollback(self):
        result = runner.ProbeResult("Stuck", "photo-needed", 1, 1, 124, 150.0, True, "TIME_BUDGET_EXCEEDED")
        self.assertFalse(runner.has_safe_progress(result))
```

- [ ] **Step 2: Run controller tests and verify RED**

Run:

```bash
python -m unittest -v tests.test_bulk_visual_run.BulkVisualRunControllerTests
```

Expected: failures for missing controller/checkpoint/summary functions.

- [ ] **Step 3: Implement validation and checkpoint helpers**

Use subprocess commands that exactly match the existing strict verification:

```python
VALIDATION_COMMAND = [
    sys.executable, "-m", "unittest", "-v",
    "tests/test_bulk_visual_*.py", "tests/test_runtime_relevance.py",
    "tests/test_apply_repair_assets.py",
]


def validate_checkpoint():
    subprocess.run("python -m unittest -v tests/test_bulk_visual_*.py tests/test_runtime_relevance.py tests/test_apply_repair_assets.py", shell=True, check=True)
    subprocess.run([sys.executable, "tools/build_runtime_review.py"], check=True)
```

Implement `commit_checkpoint` so visual-progress commits stage only:

```text
images/**
stories.txt
state/bulk_visual_repair_cursor.json
```

and cursor-only commits stage only `state/bulk_visual_repair_cursor.json`. Before every push:

```bash
git pull --rebase origin repair/story-visual-coverage
git push origin HEAD:repair/story-visual-coverage
```

If `git diff --cached --quiet` reports no staged changes, do not create an empty commit.

- [ ] **Step 4: Implement `run_bounded`**

The loop must follow this exact order for each queued row:

```text
1. Check soft deadline before START.
2. Print START with story/class/deficit.
3. Run one subprocess probe with 150-second hard timeout.
4. Print END with elapsed/rc/result/before/after.
5. If result is INVARIANT: write summary and return 3 without advancing cursor.
6. If result is SYSTEM_ERROR: write summary and return 3 without advancing cursor.
7. If after_gap < before_gap:
   a. validate_checkpoint()
   b. advance cursor to this story
   c. save cursor
   d. commit/push visual + cursor checkpoint immediately
   e. count safe progress
8. Otherwise:
   a. restore visual worktree to HEAD
   b. advance cursor in memory to this story
   c. count timeout or no-progress
9. Continue until queue exhausted or soft deadline reached.
10. At a safe bounded stop, save the latest cursor and push a cursor-only checkpoint if it changed since HEAD.
11. Rebuild the final 123-row board.
12. Return 0 only for exactly 123/123 PASS, else 10 if this invocation made any safe visual progress, else 2.
```

`has_safe_progress(result)` must be exactly `result.after_gap < result.before_gap`; do not trust child return code or registrar counts for this decision.

- [ ] **Step 5: Implement summary output**

Write `out/bulk-visual-repair/run-summary.json` and print one compact terminal summary. Use outcome strings exactly:

- `COMPLETE` for exit 0
- `PARTIAL_PROGRESS` for exit 10
- `NO_PROGRESS` for exit 2
- `INVARIANT_FAILURE` for exit 3

JSON keys:

```json
{
  "outcome": "PARTIAL_PROGRESS",
  "start_pass": 17,
  "final_pass": 18,
  "attempted": 7,
  "timed_out": 1,
  "progress_count": 1,
  "no_progress_count": 5,
  "last_attempted": {
    "photo-needed": "...",
    "logo-only": null
  }
}
```

- [ ] **Step 6: Run controller, queue, repair, and relevance tests**

Run:

```bash
python -m unittest -v \
  tests.test_bulk_visual_queue \
  tests.test_bulk_visual_run \
  tests.test_bulk_visual_repair \
  tests.test_runtime_relevance
```

Expected: all PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add tools/bulk_visual_run.py tests/test_bulk_visual_run.py
git commit -m "feat: checkpoint bounded visual repair runs"
```

---

### Task 4: Replace the unbounded Actions loop with the bounded controller

**Files:**
- Modify: `.github/workflows/bulk-visual-repair.yml`
- Modify: `tests/test_bulk_visual_workflow.py`

**Interfaces:**
- Consumes: `python tools/bulk_visual_run.py --max-stories N --max-candidates-per-beat N --story-timeout-seconds 150 --soft-deadline-seconds 1500`.
- Produces: a single serialized repair job with GitHub success for bounded outcomes 0/2/10 and GitHub failure for 3/unexpected errors.

- [ ] **Step 1: Write RED workflow-structure tests**

Extend `tests/test_bulk_visual_workflow.py` with exact assertions:

```python
def test_repair_job_has_thirty_minute_hard_timeout(self):
    text = Path(".github/workflows/bulk-visual-repair.yml").read_text(encoding="utf-8")
    self.assertIn("timeout-minutes: 30", text)


def test_workflow_calls_bounded_controller_once_and_has_no_full_backlog_probe_loop(self):
    text = Path(".github/workflows/bulk-visual-repair.yml").read_text(encoding="utf-8")
    self.assertIn("tools/bulk_visual_run.py", text)
    self.assertNotIn("for story in \"${later_stories[@]}\"", text)
    self.assertNotIn("for batch in $(seq", text)


def test_workflow_maps_two_ten_and_zero_to_success_but_three_to_failure(self):
    text = Path(".github/workflows/bulk-visual-repair.yml").read_text(encoding="utf-8")
    self.assertIn('if [ "$rc" -eq 3 ]; then exit 3; fi', text)
    self.assertIn('if [ "$rc" -eq 0 ] || [ "$rc" -eq 2 ] || [ "$rc" -eq 10 ]; then exit 0; fi', text)


def test_workflow_clamps_dispatch_story_count_to_twelve(self):
    text = Path(".github/workflows/bulk-visual-repair.yml").read_text(encoding="utf-8")
    self.assertIn("MAX_STORIES=12", text)
    self.assertIn("BATCH_STORIES", text)
```

- [ ] **Step 2: Run workflow tests and verify RED**

Run:

```bash
python -m unittest -v tests.test_bulk_visual_workflow
```

Expected: failures because the workflow still contains the old nested batch/full-backlog loops and no job timeout.

- [ ] **Step 3: Simplify the repair job**

Keep existing `workflow_dispatch` input names for compatibility with the workflow file already present on `main`. Treat `batch_stories` as a requested upper bound but clamp it to 12 in the branch workflow. Keep `max_batches` accepted but unused and label it as legacy compatibility in the branch YAML description.

The repair step should have this shape:

```bash
set -euo pipefail
requested="${BATCH_STORIES:-12}"
if ! [[ "$requested" =~ ^[0-9]+$ ]] || [ "$requested" -lt 1 ]; then requested=12; fi
MAX_STORIES=12
if [ "$requested" -lt "$MAX_STORIES" ]; then MAX_STORIES="$requested"; fi

set +e
PYTHONPATH=. python tools/bulk_visual_run.py \
  --max-stories "$MAX_STORIES" \
  --max-candidates-per-beat "$MAX_CANDIDATES" \
  --story-timeout-seconds 150 \
  --soft-deadline-seconds 1500
rc=$?
set -e

if [ "$rc" -eq 3 ]; then exit 3; fi
if [ "$rc" -eq 0 ] || [ "$rc" -eq 2 ] || [ "$rc" -eq 10 ]; then exit 0; fi
exit "$rc"
```

Set `timeout-minutes: 30` on the `repair` job. Remove the old `for batch`, `later_stories`, and nested one-story fallback loops completely.

- [ ] **Step 4: Make the summary step read `run-summary.json`**

Keep the authoritative board generation, but prepend the bounded-run outcome and counters from `out/bulk-visual-repair/run-summary.json` when present. Do not infer COMPLETE from GitHub success; COMPLETE still requires the authoritative board to be exactly 123/123 PASS.

- [ ] **Step 5: Run all workflow and strict repair tests**

Run:

```bash
python -m unittest -v \
  tests/test_bulk_visual_workflow.py \
  tests/test_bulk_visual_queue.py \
  tests/test_bulk_visual_run.py \
  tests/test_bulk_visual_repair.py \
  tests/test_runtime_relevance.py \
  tests/test_apply_repair_assets.py
```

Expected: all PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add .github/workflows/bulk-visual-repair.yml tests/test_bulk_visual_workflow.py
git commit -m "fix: bound bulk visual repair workflow"
```

---

### Task 5: Whole-branch verification and live bounded-run proof

**Files:**
- Verify: all files changed by Tasks 1-4
- Runtime artifact: `out/bulk-visual-repair/run-summary.json`
- Runtime artifact: `out/runtime-review/**`

**Interfaces:**
- Consumes: the complete redesigned runner.
- Produces: evidence that the redesign works under real GitHub-hosted network conditions without changing the visual gate.

- [ ] **Step 1: Run syntax and full local regression verification**

Run:

```bash
python -m py_compile \
  tools/bulk_visual_queue.py \
  tools/bulk_visual_run.py \
  tools/bulk_visual_repair.py

python -m unittest -v \
  tests/test_bulk_visual_*.py \
  tests/test_runtime_relevance.py \
  tests/test_apply_repair_assets.py
```

Expected: zero syntax errors and all tests PASS.

- [ ] **Step 2: Verify no runtime-gate weakening in the branch diff**

Run:

```bash
git diff origin/main...HEAD -- story_runtime.py runtime_relevance.py images/relevance.json
```

Expected for this redesign task: no redesign-specific changes to runtime PASS semantics. Any pre-existing PR #2 changes must be reviewed against the already-approved strict contract; do not add new weakening here.

- [ ] **Step 3: Verify the old long-running workflow is no longer active before dispatch**

In GitHub Actions, confirm no `Bulk visual repair` repair job is currently `in_progress` on `repair/story-visual-coverage`. If one is active, cancel it in the GitHub UI before proceeding. Do not run two branch writers concurrently.

- [ ] **Step 4: Start one fresh manual bounded run**

Dispatch **Bulk visual repair** on branch `repair/story-visual-coverage` with:

```text
batch_stories = 12
max_candidates_per_beat = 12
max_batches = 12   # legacy input; ignored by redesigned runner
```

Expected live properties:

```text
- job has timeout-minutes: 30
- no more than 12 START story= lines
- every START has one END line unless the job itself is externally cancelled
- no individual probe exceeds about 150 seconds plus the short termination grace period
- GitHub success is allowed for COMPLETE, PARTIAL_PROGRESS, or NO_PROGRESS
- invariant/system/push/test failures still produce GitHub Failure
```

- [ ] **Step 5: Verify immediate checkpoint behavior**

If any story shows `after < before`, confirm before the next story progresses materially that the log runs strict tests/runtime review and the branch receives a checkpoint commit containing only allowed paths:

```text
images/**
stories.txt
state/bulk_visual_repair_cursor.json
```

If the run makes no visual progress, confirm the visual working tree is restored and only the cursor state is pushed at safe completion.

- [ ] **Step 6: Verify persisted-cursor behavior with a second fresh run**

Unless the first run reaches 123/123, dispatch a second fresh run with the same inputs. Compare the first `START story=` entries against the prior run. The second run must begin after the stored cursor for the relevant class instead of repeating the same hard prefix.

- [ ] **Step 7: Verify authoritative board non-regression**

Read the final job summary and `run-summary.json`. Record:

```text
start_pass
final_pass
attempted
timed_out
progress_count
no_progress_count
outcome
```

Require `final_pass >= start_pass`. Do not claim catalogue completion unless the authoritative board is exactly `123/123 PASS`.

- [ ] **Step 8: Final whole-branch review**

Review the PR #2 diff for:

```text
- no unbounded backlog loops
- no parallel writer paths
- no cursor advancement past invariant failure
- no timeout path that can checkpoint unvalidated visual changes
- no gate weakening
- no Story publishing enablement
```

- [ ] **Step 9: Commit any verification-only test/doc correction, if needed**

Only if verification exposed a test/documentation mismatch that requires a committed correction, make that correction with its own RED→GREEN cycle and commit it separately. Otherwise create no empty commit.

---

## Plan Self-Review Result

- Spec coverage: all approved requirements are mapped to Tasks 1-5, including class-aware ordering, persisted cursor, 12-story cap, 150-second story timeout, 25-minute soft deadline, 30-minute Actions timeout, immediate validated checkpoints, timeout rollback, observability, and exit semantics.
- Placeholder scan: no `TBD`, `TODO`, deferred implementation, or unspecified error-handling steps remain.
- Type/interface consistency: queue functions in Task 1 are consumed by the controller in Tasks 2-3; `ProbeResult` and controller exit codes are consumed by the workflow in Task 4; the live verification in Task 5 checks those same exact interfaces.
- Scope boundary: no runtime relevance rule, approval-ledger rule, publishing behavior, or parallel writer is changed by this plan.
