"""Deterministic, non-approving output for work requiring human sourcing."""
from __future__ import annotations
import json
from pathlib import Path
from tools.bulk_visual_history import load_history
from tools.bulk_visual_sources import plan_story_beats, story_source_strategy

CURATION_PATH = Path("out/bulk-visual-repair/curation-required.json")

def write_curation(rows, path=CURATION_PATH, records=None):
    records = load_history() if records is None else records
    entries = []
    for row in sorted((r for r in rows if r.status != "PASS"), key=lambda r: r.story.casefold()):
        beats = plan_story_beats(row.story)
        history = [r for r in records if r.get("story") == row.story]
        entries.append({
            "story": row.story, "deficit": {"photos": row.need_photos, "logo": int(row.need_logo)},
            "required_identity": {"type": beats[0].entity_kind if beats else "unknown",
                "aliases": list(beats[0].required_identity) if beats else [],
                "context": list(beats[0].entity_context) if beats else [],
                "incompatible_senses": list(beats[0].incompatible_context) if beats else []},
            "missing_beats": [b.key for b in beats][:4],
            "sources_exhausted": sorted({r.get("source") for r in history if r.get("source")}),
            "rejected_candidates": [{"source_id": r["source_id"],
                "reason": str(r.get("reason", ""))[:160]} for r in history
                if r.get("source_id")][-16:],
            "queries_attempted": list(dict.fromkeys(str(r.get("query"))[:160] for r in history
                if r.get("query")))[-24:],
            "constraints": ["local usable media", "traceable provenance", "compatible license",
                "exact identity", "DIRECT or STRONG_CONTEXT", "no duplicate"],
            "recommended_source": ("verified Wikidata P154 plus unique official domain"
                if row.need_logo and not row.need_photos else
                " then ".join(story_source_strategy(row.story, beats))),
        })
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "entries": entries}, ensure_ascii=False,
        indent=2) + "\n", encoding="utf-8")
    return path
