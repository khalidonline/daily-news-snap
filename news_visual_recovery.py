"""Deterministic recovery helpers for scheduled News visuals."""

from __future__ import annotations

import json
import re
from pathlib import Path


ALLOWED_TARGET_KINDS = frozenset({
    "person", "organization", "place", "object", "context",
})
MAX_VISUAL_TARGETS = 8


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _identity(value):
    return re.sub(r"[^a-z0-9\u0600-\u06ff]+", "", _clean(value).casefold())


def normalize_visual_targets(story):
    """Return a bounded, typed and deduplicated visual fallback plan."""
    raw_targets = story.get("visual_targets") or []
    if not raw_targets:
        raw_targets = [
            {"kind": "context", "name_en": query, "name_ar": ""}
            for query in story.get("image_queries", []) or []
        ] + [
            {"kind": "context", "name_en": "", "name_ar": query}
            for query in story.get("image_queries_ar", []) or []
        ]

    normalized = []
    seen = set()
    for raw in raw_targets:
        if not isinstance(raw, dict):
            continue
        kind = _clean(raw.get("kind")).casefold()
        name_en = _clean(raw.get("name_en"))
        name_ar = _clean(raw.get("name_ar"))
        if kind not in ALLOWED_TARGET_KINDS or not (name_en or name_ar):
            continue
        key = (kind, _identity(name_en) or _identity(name_ar))
        if key in seen:
            continue
        seen.add(key)
        normalized.append({
            "kind": kind,
            "name_en": name_en,
            "name_ar": name_ar,
        })
        if len(normalized) == MAX_VISUAL_TARGETS:
            break
    return normalized


def exact_logo_for_targets(targets, logos_dir, index_path):
    """Resolve a current logo only from a canonical organization identity."""
    logos_dir = Path(logos_dir)
    try:
        index = json.loads(Path(index_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None

    organizations = {
        _identity(name)
        for target in targets
        if target.get("kind") == "organization"
        for name in (target.get("name_en"), target.get("name_ar"))
        if _identity(name)
    }
    for key, aliases in index.items():
        aliases = aliases if isinstance(aliases, list) else []
        canonical_alias = _clean(aliases[0]) if aliases else _clean(key)
        canonical_names = {
            _identity(key),
            _identity(str(key).split(".")[0]),
            _identity(canonical_alias),
        }
        if not organizations.intersection(canonical_names):
            continue
        matches = sorted(logos_dir.glob(f"{key}-current.*"))
        if not matches:
            matches = sorted(logos_dir.glob(f"{key}.*"))
        if matches:
            return matches[0], canonical_alias
        # Only registered canonical domains may authorize an online lookup.
        # Never derive a domain from model output or an ambiguous alias.
        if re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", key):
            import logo_fetch
            try:
                old_dir = logo_fetch.LOGOS_DIR
                logo_fetch.LOGOS_DIR = logos_dir
                logos_dir.mkdir(parents=True, exist_ok=True)
                fetched = logo_fetch.fetch_current(
                    key, [canonical_alias], require_domain=key
                )
                if fetched and Path(fetched).is_file():
                    return Path(fetched), canonical_alias
            except Exception as exc:
                print(f"  ! verified logo lookup failed for {key}: {exc}")
            finally:
                logo_fetch.LOGOS_DIR = old_dir
    return None, None
