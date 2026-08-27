"""Durable advisory memory for bounded bulk-visual controller runs.

Nothing in this file is an approval signal.  The history may only avoid
repeating deterministic discovery/validation work; runtime coverage remains
the sole authority for visual progress.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile


HISTORY_PATH = Path("state/bulk_visual_failure_history.json")
MAX_DIAGNOSTICS = 500
MAX_REJECTIONS = 2000
MAX_QUERY_SETS = 1000


def empty_history():
    return {"version": 1, "candidate_rejections": [], "complete_query_sets": [],
            "diagnostics": []}


def load_history(path=HISTORY_PATH):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return empty_history()
    if not isinstance(value, dict):
        return empty_history()
    clean = empty_history()
    for key in ("candidate_rejections", "complete_query_sets", "diagnostics"):
        if isinstance(value.get(key), list):
            clean[key] = [item for item in value[key] if isinstance(item, dict)]
    return clean


def save_history(history, path=HISTORY_PATH):
    """Atomically store bounded data so a killed probe cannot corrupt state."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    bounded = {"version": 1,
               "candidate_rejections": history.get("candidate_rejections", [])[-MAX_REJECTIONS:],
               "complete_query_sets": history.get("complete_query_sets", [])[-MAX_QUERY_SETS:],
               "diagnostics": history.get("diagnostics", [])[-MAX_DIAGNOSTICS:]}
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", delete=False) as handle:
        json.dump(bounded, handle, ensure_ascii=False, indent=2)
        handle.write("\n"); temporary = Path(handle.name)
    temporary.replace(path)


def query_set_fingerprint(queries):
    """Fingerprint the complete query set independent of incidental ordering."""
    complete_set = sorted(set(str(query) for query in queries))
    encoded = json.dumps(complete_set, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def rejected_source_ids(history, story):
    return {item["source_id"] for item in history["candidate_rejections"]
            if item.get("story") == story and item.get("source_id")}


def query_set_complete(history, story, beat, source, fingerprint):
    return any(item.get("story") == story and item.get("beat") == beat
               and item.get("source") == source and item.get("fingerprint") == fingerprint
               for item in history["complete_query_sets"])


def mark_query_set_complete(history, story, beat, source, fingerprint):
    record = {"story": story, "beat": beat, "source": source,
              "fingerprint": fingerprint}
    if not query_set_complete(history, story, beat, source, fingerprint):
        history["complete_query_sets"].append(record)


def record_attempt(history, record):
    """Retain telemetry and only deterministic, source-addressable rejections."""
    if record.get("result") == "ACCEPTED":
        return
    diagnostic = {key: record[key] for key in
                  ("story", "beat", "source", "source_id", "result", "reason")
                  if key in record}
    history["diagnostics"].append(diagnostic)
    result, reason = record.get("result"), str(record.get("reason", "")).casefold()
    deterministic = (result in {"IDENTITY_UNPROVEN", "DUPLICATE_ONLY"} or
                     result == "VALIDATION_ERROR" and any(term in reason for term in (
                         "image too small", "unsupported", "invalid media", "flat graphic",
                         "logo-like", "perceptual hash unavailable", "wrong_entity",
                         "wrong entity", "incompatible")))
    source_id = record.get("source_id")
    if deterministic and source_id:
        item = {"story": record.get("story"), "source": record.get("source"),
                "source_id": source_id, "result": result}
        if item not in history["candidate_rejections"]:
            history["candidate_rejections"].append(item)
