"""Bounded, advisory failure memory for visual discovery.

This state can suppress known-useless work, but is deliberately incapable of
registering an asset or influencing runtime coverage.
"""

from __future__ import annotations

from collections import deque
import json
from pathlib import Path

HISTORY_PATH = Path("out/bulk-visual-repair/diagnostic-history.json")
MAX_RECORDS = 512
MAX_PER_STORY = 64
DETERMINISTIC_REJECTIONS = frozenset({
    "WRONG_ENTITY", "DUPLICATE_ONLY", "INCOMPATIBLE_ENTITY_SENSE",
    "INVALID_MEDIA_TYPE", "IDENTITY_UNPROVEN",
})
EXHAUSTED_RESULTS = frozenset({
    "NO_SAFE_CANDIDATE", "SOURCE_DISCOVERY_BUDGET_EXCEEDED",
    "DISCOVERY_ENTITY_CONFLICT_SKIPPED",
})


def _bounded(value, length=240):
    return str(value or "")[:length]


def load_history(path=HISTORY_PATH):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        records = payload.get("records", [])
        return records[-MAX_RECORDS:] if isinstance(records, list) else []
    except (OSError, ValueError, TypeError):
        return []


def remember(record, path=HISTORY_PATH):
    """Persist only bounded failure diagnostics; acceptances are never cached."""
    result = _bounded(record.get("result"), 64)
    if result == "ACCEPTED":
        return
    item = {key: _bounded(record.get(key)) for key in
            ("story", "kind", "beat", "source", "source_id", "query",
             "candidate", "result", "reason") if record.get(key) is not None}
    records = load_history(path)
    story = item.get("story", "")
    same = deque((r for r in records if r.get("story") == story), maxlen=MAX_PER_STORY)
    others = [r for r in records if r.get("story") != story]
    same.append(item)
    records = (others + list(same))[-MAX_RECORDS:]
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "records": records},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class FailureHistory:
    def __init__(self, story, records=None):
        self.story = story
        self.records = [r for r in (records if records is not None else load_history())
                        if r.get("story") == story]

    @property
    def rejected_source_ids(self):
        return {r.get("source_id") for r in self.records
                if r.get("source_id") and r.get("result") in DETERMINISTIC_REJECTIONS}

    def query_exhausted(self, source, beat, queries):
        wanted = {_bounded(q, 160).casefold() for q in queries}
        return bool(wanted) and wanted.issubset({
            _bounded(r.get("query"), 160).casefold() for r in self.records
            if r.get("source") == source and r.get("beat") == beat
            and r.get("result") in EXHAUSTED_RESULTS
        })
