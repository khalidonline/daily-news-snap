#!/usr/bin/env python3
"""Runtime-safe Story Bot entrypoint.

The old catalogue could call a story READY while the renderer could only see
one local file. This entrypoint makes the runtime itself authoritative:
4 distinct, reviewed, relevant local photos + 1 local logo are required before
research starts. It also exposes the renderer only to the approved local image
rows for the selected story.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import image_precheck as ipc
import news_bot as nb
import story_bot as sb
import story_focus
import story_editorial_runtime
import story_visual_state
import city_visual_v3
from runtime_relevance import asset_countable, runtime_pass, runtime_status

# Story to Snapchat always enters through this guarded runtime. Apply the
# editorial subject lock first, then cost-controlled editorial caching, then
# the city-only selector. The revision prompt includes the same reviewed local
# visual inventory that Story Focus appends during the paid research call.
story_focus.configure(sb)


def _editorial_prompt_for_revision():
    inventory = ""
    try:
        inventory = story_focus.runtime_visual_inventory_prompt(nb.IMAGES_INDEX)
    except Exception:
        inventory = ""
    return sb.SYSTEM_PROMPT + inventory


sb.editorial_prompt_for_revision = _editorial_prompt_for_revision
story_editorial_runtime.configure(sb)
city_visual_v3.configure(sb)
# Visual-state reuse wraps the final city/non-city selector so approved frames
# keep all existing relevance/era/haze protections and failed slots alone are
# reopened during visual_only repair.
story_visual_state.configure(sb)


def _matches_story(entry, story):
    aliases = [a for a in sb.story_aliases(story) if a]
    persons = sb._STORY_PERSONS.get(str(story).strip()) or []
    return story_focus.catalog_tags_match_aliases(
        entry.get("tags", []), aliases + persons
    )


def approved_runtime_visuals(story):
    """Return distinct approved local photos plus local logos for ``story``."""
    photos = []
    for entry in nb.load_local_images():
        path = entry["path"]
        if not path.exists() or not _matches_story(entry, story):
            continue
        if not asset_countable(path.name, story):
            continue
        photos.append(path)

    kept, hashes, shas = [], [], set()
    for path in photos:
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        if digest in shas:
            continue
        dh = ipc.dhash(path)
        if dh is None:
            continue
        if any(bin(dh ^ old).count("1") <= ipc.DHASH_MAX_DISTANCE
               for old in hashes):
            continue
        shas.add(digest)
        hashes.append(dh)
        kept.append(path)

    # Logo resolution in story_bot is already local-file based and uses the
    # story's declared identity. We deliberately ignore its photo result here.
    _, logos = sb.resolve_runtime_visuals(story)
    return kept, logos


def coverage(story):
    photos, logos = approved_runtime_visuals(story)
    return photos, logos, runtime_status(len(photos), len(logos))


def _eligible_story(story):
    photos, logos, status = coverage(story)
    print(f"    runtime relevance: {status} "
          f"({len(photos)} approved photos, {len(logos)} logo(s))")
    return runtime_pass(len(photos), len(logos))


def _fresh_candidates(pool):
    stories = [s for s in sb.load_stories()
               if sb._STORY_POOLS.get(s, "general") == pool]
    used = {e["story"] for e in sb.load_used()}
    used |= {e["story"] for e in sb.load_skipped()}
    used |= sb._UNIDENTIFIED

    used_subjects = set()
    try:
        cutoff = (datetime.now() - timedelta(days=sb.SUBJECT_COOLDOWN_DAYS)).isoformat()
        for row in json.loads(sb.USED_FILE.read_text(encoding="utf-8")):
            if row.get("at", "") >= cutoff:
                used_subjects |= sb._subject_keys(row.get("story", ""))
    except Exception:
        for story in used:
            used_subjects |= sb._subject_keys(story)

    return [s for s in stories
            if s not in used and not (sb._subject_keys(s) & used_subjects)]


def choose_runtime_story():
    mix = sb.load_mix()
    preferred = sb.choose_pool(mix)
    pools = [preferred, "general" if preferred == "saudi" else "saudi"]
    for pool in pools:
        candidates = _fresh_candidates(pool)
        good = [s for s in candidates if _eligible_story(s)]
        if not good:
            continue
        seed = hashlib.md5(datetime.now().date().isoformat().encode()).hexdigest()
        story = good[int(seed, 16) % len(good)]
        print(f"    runtime gate: {len(good)} PASS stories available in {pool}")
        return story
    return ""


def _filtered_index(story, approved_paths):
    """Write a story-specific image index containing only approved files."""
    allowed = {Path(p).name for p in approved_paths}
    source = nb.IMAGES_INDEX
    lines = []
    try:
        raw = source.read_text(encoding="utf-8").splitlines()
    except OSError:
        raw = []
    for line in raw:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        filename = stripped.split("|", 1)[0].strip()
        if filename in allowed:
            lines.append(line)
    sb.OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = sb.OUT_DIR / "runtime-images-approved.txt"
    dest.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return dest


def main():
    if sb.STORY:
        story = sb.resolve_story_input(sb.STORY)
    else:
        story = choose_runtime_story()

    if not story:
        raise SystemExit("no runtime-PASS story available (needs 4 approved photos + logo)")

    photos, logos, status = coverage(story)
    if not runtime_pass(len(photos), len(logos)):
        raise SystemExit(
            f"story blocked by runtime relevance gate: {status}; "
            f"{len(photos)} approved photos, {len(logos)} logo(s): {story}")

    # Give the existing renderer only the approved rows for this story. This is
    # stronger than merely changing the audit: rejected/unreviewed local assets
    # are invisible to fetch_local_photo for this run.
    filtered = _filtered_index(story, photos)
    nb.IMAGES_INDEX = filtered
    os.environ["IMAGES_INDEX"] = str(filtered)
    sb.STORY = story
    print(f"    runtime gate PASS: {story}")
    print("    approved photos: " + ", ".join(p.name for p in photos))
    print("    logo(s): " + ", ".join(p.name for p in logos))
    sb.main()


if __name__ == "__main__":
    main()
