#!/usr/bin/env python3
"""Bounded lifecycle primitives for single-story visual repair probes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from dataclasses import asdict
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
from tools.bulk_visual_repair import _write_unresolved


OUT_DIR = Path("out/bulk-visual-repair")
FAILURE_HISTORY_PATH = "state/bulk_visual_failure_history.json"
VISUAL_PATHS = ("images", "stories.txt")
ATTEMPTED_STATE_PATHS = (*VISUAL_PATHS, FAILURE_HISTORY_PATH)
TOTAL_STORIES = 123


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


@dataclass(frozen=True)
class RunSummary:
    outcome: str
    start_pass: int
    final_pass: int
    attempted: int
    timed_out: int
    progress_count: int
    no_progress_count: int
    last_attempted: dict[str, str | None]


def gap(row: CoverageRow) -> int:
    """Return the runtime-visible visual deficit for a coverage row."""

    return row.need_photos + int(row.need_logo)


def runtime_row(story: str) -> CoverageRow:
    """Reload story metadata and return fresh authoritative runtime coverage."""

    sb.load_stories()
    return build_board([story])[0]


def _git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], check=check, text=True, capture_output=True,
    )


def visual_worktree_status() -> list[str]:
    result = _git(["status", "--porcelain", "--", *VISUAL_PATHS])
    return [line for line in result.stdout.splitlines() if line.strip()]


def restore_visual_worktree(*, restore_history: bool = True) -> None:
    """Restore attempted state; normal failures retain advisory diagnostics."""

    paths = ATTEMPTED_STATE_PATHS if restore_history else VISUAL_PATHS
    _git([
        "restore", "--source=HEAD", "--staged", "--worktree", "--",
        *paths,
    ])
    _git(["clean", "-fd", "--", "images"])


def assert_clean_visual_worktree() -> None:
    dirty = visual_worktree_status()
    if dirty:
        raise RuntimeError(
            "visual worktree must be clean before bounded repair: " + "; ".join(dirty)
        )


def _spawn_story_process(story: str, max_candidates: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "tools/bulk_visual_repair.py",
            "--story", story,
            "--batch-stories", "1",
            "--max-candidates-per-beat", str(max_candidates),
        ],
        start_new_session=True,
    )


def _terminate_process_group(proc: subprocess.Popen) -> None:
    """Terminate the entire repair subprocess group, escalating after grace."""

    # ``Popen.pid`` is always an integer in production.  Keeping this helper
    # tolerant of process-shaped test doubles lets lifecycle tests focus on
    # post-timeout coverage classification without creating a real child.
    if not isinstance(proc.pid, int):
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        # The child may have exited between the timed wait and signalling.
        proc.wait()
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        # Always reap after escalation; leaving a zombie is not a completed
        # timeout lifecycle even when the process group disappeared first.
        proc.wait()


def run_story_probe(
    row: CoverageRow,
    max_candidates: int,
    timeout_seconds: int = 150,
) -> ProbeResult:
    """Run one repair process and classify it using refreshed runtime coverage."""

    started = time.monotonic()
    proc = _spawn_story_process(row.story, max_candidates)
    timed_out = False
    try:
        returncode = proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_group(proc)
        returncode = 124

    refreshed = runtime_row(row.story)
    before_gap = gap(row)
    after_gap = gap(refreshed)
    if returncode == 3:
        result = "INVARIANT"
    elif timed_out:
        result = "TIME_BUDGET_EXCEEDED"
    elif after_gap < before_gap:
        result = "SAFE_PROGRESS"
    elif returncode in {0, 2, 10}:
        result = "NO_PROGRESS"
    else:
        result = "SYSTEM_ERROR"

    return ProbeResult(
        story=row.story,
        queue_class="photo-needed" if row.need_photos else "logo-only",
        before_gap=before_gap,
        after_gap=after_gap,
        returncode=returncode,
        elapsed_seconds=time.monotonic() - started,
        timed_out=timed_out,
        result=result,
    )


def has_safe_progress(result: ProbeResult) -> bool:
    """Trust only a reduction reported by fresh runtime coverage."""

    return result.after_gap < result.before_gap


def validate_checkpoint() -> None:
    """Run the strict visual tests and rebuild the runtime review artifact."""

    subprocess.run(
        "python -m unittest -v tests/test_bulk_visual_*.py "
        "tests/test_runtime_relevance.py tests/test_apply_repair_assets.py",
        shell=True,
        check=True,
    )
    subprocess.run([sys.executable, "tools/build_runtime_review.py"], check=True)


def commit_checkpoint(
    cursor: dict[str, str | None],
    message: str,
    visual_progress: bool,
) -> None:
    """Commit and push exactly the durable state allowed for this checkpoint."""

    del cursor  # The caller persists it before invoking this side-effect boundary.
    paths = ["state/bulk_visual_repair_cursor.json", FAILURE_HISTORY_PATH]
    if visual_progress:
        paths = ["images", "stories.txt", *paths]
    _git(["add", "-A", "--", *paths])
    staged = _git(["diff", "--cached", "--quiet"], check=False)
    if staged.returncode == 0:
        return
    if staged.returncode != 1:
        raise subprocess.CalledProcessError(staged.returncode, staged.args)
    _git(["commit", "-m", message])
    _git(["pull", "--rebase", "origin", "repair/story-visual-coverage"])
    _git(["push", "origin", "HEAD:repair/story-visual-coverage"])


def _initial_and_queue(max_stories: int):
    assert_clean_visual_worktree()
    rows = build_board()
    cursor = load_cursor()
    # This is the security boundary for every caller, not merely the workflow
    # wrapper: no invocation can probe more than twelve stories.
    limit = min(12, max(0, int(max_stories)))
    return rows, build_run_queue(rows, cursor, limit), cursor


def _final_board() -> list[CoverageRow]:
    sb.load_stories()
    return build_board()


def _pass_count(rows: list[CoverageRow]) -> int:
    return sum(row.status == "PASS" for row in rows)


def board_regressions(
    accepted: list[CoverageRow], candidate: list[CoverageRow],
) -> list[str]:
    """Name stories whose authoritative coverage regressed or disappeared."""

    current = {row.story: row for row in candidate}
    regressions = []
    for previous in accepted:
        row = current.get(previous.story)
        if row is None or gap(row) > gap(previous):
            regressions.append(previous.story)
    return sorted(regressions, key=str.casefold)


def write_summary(
    summary: RunSummary,
    path: str | Path = OUT_DIR / "run-summary.json",
) -> Path:
    """Write the machine summary and emit one compact terminal summary."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "SUMMARY "
        f"outcome={summary.outcome} pass={summary.start_pass}->{summary.final_pass} "
        f"attempted={summary.attempted} timed_out={summary.timed_out} "
        f"progress={summary.progress_count} no_progress={summary.no_progress_count}"
    )
    return path


def run_bounded(
    max_stories: int = 12,
    max_candidates: int = 12,
    story_timeout_seconds: int = 150,
    soft_deadline_seconds: int = 1500,
) -> int:
    """Run one bounded, resumable, fail-closed repair slice."""

    started = time.monotonic()
    initial, queue, cursor = _initial_and_queue(max_stories)
    accepted_board = initial
    start_pass = _pass_count(initial)
    attempted = timed_out = progress_count = no_progress_count = 0
    last_attempted = {"photo-needed": None, "logo-only": None}

    def finish(code: int, outcome: str) -> int:
        final = _final_board()
        _write_unresolved(final, OUT_DIR / "curation-required.json")
        write_summary(RunSummary(
            outcome=outcome,
            start_pass=start_pass,
            final_pass=_pass_count(final),
            attempted=attempted,
            timed_out=timed_out,
            progress_count=progress_count,
            no_progress_count=no_progress_count,
            last_attempted=last_attempted,
        ))
        return code

    for item in queue:
        # Do not begin work that cannot fit inside the controller's start budget.
        if time.monotonic() - started + story_timeout_seconds > soft_deadline_seconds:
            break
        print(
            f"START story={item.story!r} class="
            f"{'photo-needed' if item.need_photos else 'logo-only'} deficit={gap(item)}"
        )
        result = run_story_probe(item, max_candidates, story_timeout_seconds)
        attempted += 1
        last_attempted[result.queue_class] = item.story
        print(
            f"END story={item.story!r} elapsed={result.elapsed_seconds:.1f}s "
            f"rc={result.returncode} result={result.result} "
            f"before={result.before_gap} after={result.after_gap}"
        )

        if result.result in {"INVARIANT", "SYSTEM_ERROR"}:
            restore_visual_worktree()
            return finish(3, "INVARIANT_FAILURE")

        if result.timed_out:
            timed_out += 1
        if has_safe_progress(result):
            candidate_board = _final_board()
            regressions = board_regressions(accepted_board, candidate_board)
            if regressions:
                print("REGRESSION stories=" + ", ".join(regressions))
                restore_visual_worktree()
                return finish(3, "INVARIANT_FAILURE")
            validate_checkpoint()
            cursor = advance_cursor(cursor, item)
            save_cursor(cursor)
            commit_checkpoint(
                cursor,
                message=f"repair: checkpoint visual progress for {item.story}",
                visual_progress=True,
            )
            accepted_board = candidate_board
            progress_count += 1
        else:
            restore_visual_worktree(restore_history=False)
            cursor = advance_cursor(cursor, item)
            if not result.timed_out:
                no_progress_count += 1

    save_cursor(cursor)
    commit_checkpoint(
        cursor,
        message="chore: advance bulk visual repair cursor",
        visual_progress=False,
    )
    final = _final_board()
    _write_unresolved(final, OUT_DIR / "curation-required.json")
    final_pass = _pass_count(final)
    if final_pass == TOTAL_STORIES and len(final) == TOTAL_STORIES:
        code, outcome = 0, "COMPLETE"
    elif progress_count:
        code, outcome = 10, "PARTIAL_PROGRESS"
    else:
        code, outcome = 2, "NO_PROGRESS"
    write_summary(RunSummary(
        outcome, start_pass, final_pass, attempted, timed_out,
        progress_count, no_progress_count, last_attempted,
    ))
    return code


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def main(argv: list[str] | None = None) -> int:
    """Parse the stable workflow CLI and run one bounded repair slice."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-stories", type=_positive_int, default=12)
    parser.add_argument(
        "--max-candidates-per-beat", type=_positive_int, default=12,
    )
    parser.add_argument(
        "--story-timeout-seconds", type=_positive_int, default=150,
    )
    parser.add_argument(
        "--soft-deadline-seconds", type=_positive_int, default=1500,
    )
    args = parser.parse_args(argv)
    return run_bounded(
        max_stories=args.max_stories,
        max_candidates=args.max_candidates_per_beat,
        story_timeout_seconds=args.story_timeout_seconds,
        soft_deadline_seconds=args.soft_deadline_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
