"""Deterministic source ordering derived only from declared story metadata."""

from __future__ import annotations

import story_bot as sb


def story_source_strategy(story, beats=None):
    """Return bounded adapter priority without changing any acceptance gate."""
    beats = tuple(beats or ())
    kind = getattr(beats[0], "entity_kind", "") if beats else ""
    contexts = {str(value).strip().casefold() for beat in beats
                for value in getattr(beat, "entity_context", ()) if str(value).strip()}
    text = str(story).casefold()
    domain = sb.story_logo_domain(story)
    gulf = bool(contexts & {"saudi", "gulf", "ksa", "السعودية", "الخليج"}) or any(
        token in text for token in ("السعود", "الرياض", "جدة", "دبي", "إمارات"))
    company = bool(domain) or bool(contexts & {
        "company", "corporation", "retail", "delivery", "ecommerce", "food",
        "airline", "bank", "telecom",
    })
    if kind == "person":
        return ("commons", "loc", "first-party", "openverse")
    if gulf and company:
        return ("first-party", "commons", "loc", "openverse")
    if company:
        return ("first-party", "commons", "openverse", "loc")
    if contexts & {"history", "historical", "archive", "place", "city", "location"}:
        return ("commons", "loc", "openverse", "first-party")
    if contexts & {"product", "invention"}:
        return ("commons", "first-party", "loc", "openverse")
    return ("commons", "loc", "openverse", "first-party")
