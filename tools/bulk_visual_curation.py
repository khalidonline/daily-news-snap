"""Deterministic, informational curation output for unresolved visual stories."""

from __future__ import annotations

import json
from pathlib import Path

from tools.bulk_visual_sources import plan_story_beats
from tools.bulk_visual_strategy import story_source_strategy


CURATION_PATH = Path("out/bulk-visual-repair/curation-required.json")
MAX_REJECTIONS_PER_STORY = 16
MAX_QUERY_SETS_PER_STORY = 24
CONSTRAINTS = [
    "local usable media",
    "traceable provenance",
    "compatible license",
    "exact identity",
    "DIRECT or STRONG_CONTEXT",
    "no duplicate",
    "verified logo identity",
]


def _diagnostic_reason(history, story, source_id):
    for item in reversed(history.get("diagnostics", [])):
        if item.get("story") == story and item.get("source_id") == source_id:
            return str(item.get("reason", ""))[:160]
    return ""


def _completed_sets(history, story):
    rows = [
        {"beat": str(item.get("beat", ""))[:80],
         "source": str(item.get("source", ""))[:80],
         "fingerprint": str(item.get("fingerprint", ""))[:128]}
        for item in history.get("complete_query_sets", [])
        if item.get("story") == story
    ]
    rows.sort(key=lambda item: (item["beat"].casefold(), item["source"].casefold(),
                                item["fingerprint"]))
    return rows[:MAX_QUERY_SETS_PER_STORY]


def _rejections(history, story):
    rows = []
    for item in history.get("candidate_rejections", []):
        if item.get("story") != story or not item.get("source_id"):
            continue
        reason = str(item.get("reason", ""))[:160] or _diagnostic_reason(
            history, story, item.get("source_id"))
        rows.append({
            "source_id": str(item.get("source_id"))[:240],
            "source": str(item.get("source", ""))[:80],
            "result": str(item.get("result", ""))[:80],
            "reason": reason,
        })
    rows.sort(key=lambda item: (item["source"].casefold(), item["source_id"],
                                item["result"], item["reason"]))
    return rows[:MAX_REJECTIONS_PER_STORY]


def write_curation(rows, history, path=CURATION_PATH):
    """Write the complete unresolved board without mutating runtime state."""
    entries = []
    for row in sorted((item for item in rows if item.status != "PASS"),
                      key=lambda item: item.story.casefold()):
        beats = plan_story_beats(row.story)
        first = beats[0] if beats else None
        strategy = story_source_strategy(row.story, beats)
        logo_only = row.need_logo and not row.need_photos
        entries.append({
            "story": row.story,
            "deficit": {"photos": row.need_photos, "logo": int(row.need_logo)},
            "required_identity": {
                "type": getattr(first, "entity_kind", "unknown") if first else "unknown",
                "aliases": list(getattr(first, "required_identity", ())) if first else [],
                "context": list(getattr(first, "entity_context", ())) if first else [],
                "incompatible_senses": list(getattr(first, "incompatible_context", ())) if first else [],
            },
            "missing_beats": [beat.key for beat in beats][:4],
            "completed_query_sets": _completed_sets(history, row.story),
            "rejected_candidates": _rejections(history, row.story),
            "constraints": list(CONSTRAINTS),
            "recommended_source": (
                "verified Wikidata P154 plus unique official domain"
                if logo_only else " then ".join(strategy)
            ),
        })
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "entries": entries}, ensure_ascii=False,
                               indent=2) + "\n", encoding="utf-8")
    return path
