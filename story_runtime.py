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
from runtime_relevance import (
    asset_countable,
    runtime_contract_slots,
    runtime_pass,
    runtime_status,
)


def _matches_story(entry, story):
    aliases = [a for a in sb.story_aliases(story) if a]
    persons = sb._STORY_PERSONS.get(str(story).strip()) or []
    phrases = {a.casefold() for a in aliases + persons}
    words = set()
    for q in phrases:
        words |= {t for t in q.replace(",", " ").split() if len(t) > 2}
    tags = {t.casefold() for t in entry.get("tags", [])}
    return any(tag in phrases or (" " not in tag and tag in words)
               for tag in tags)


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


def _approved_match_index(photo, approved_paths):
    """Which approved source is this rendered/selected photo, if any?"""
    if not photo:
        return None
    try:
        candidate = Path(photo).resolve()
    except (OSError, TypeError, ValueError):
        candidate = None
    for i, approved in enumerate(approved_paths):
        try:
            if candidate is not None and candidate == Path(approved).resolve():
                return i
        except (OSError, TypeError, ValueError):
            pass

    try:
        digest = sb._photo_digest(photo)
    except Exception:
        return None
    if digest is None:
        return None
    for i, approved in enumerate(approved_paths):
        try:
            if sb.same_picture(digest, sb._photo_digest(approved)):
                return i
        except Exception:
            continue
    return None


def _is_logo_visual(photo):
    """story_bot marks rendered logo cards with a sidecar exemption."""
    if not photo:
        return False
    try:
        return Path(str(photo) + ".exempt").exists()
    except (OSError, TypeError, ValueError):
        return False


def _enforce_approved_photo_contract(brief, selected, approved_paths):
    """Make a runtime PASS visible: at least four frames use approved photos.

    ``story_bot`` remains responsible for frame-aware portrait/logo/search
    choices. This final runtime pass only replaces slots selected by the shared
    contract planner, using the same distinct approved pool that opened the
    gate. That keeps person identity protected and preserves one logo while
    preventing typography or an extra logo from hiding an already-reviewed
    photo library.
    """
    if selected is None:
        return None
    selected = list(selected)
    approved_paths = [Path(p) for p in approved_paths]
    target = min(4, len(brief.get("frames", [])), len(approved_paths))
    if target <= 0:
        return selected

    matched = []
    used_approved = set()
    approved_flags = []
    for photo in selected:
        idx = _approved_match_index(photo, approved_paths)
        if idx is not None and idx not in used_approved:
            approved_flags.append(True)
            used_approved.add(idx)
            matched.append(idx)
        else:
            approved_flags.append(False)
            matched.append(None)

    logo_flags = [_is_logo_visual(photo) for photo in selected]
    slots = runtime_contract_slots(
        brief, selected, approved_flags, logo_flags, target=target
    )
    need = max(0, target - sum(approved_flags))
    if len(slots) < need:
        raise SystemExit(
            "runtime photo contract could not place four approved photos "
            "without overwriting a protected person frame or the deck's "
            "only logo"
        )

    unused = [p for i, p in enumerate(approved_paths) if i not in used_approved]
    injected = []
    for slot, path in zip(slots, unused):
        selected[slot] = str(path)
        injected.append(str(path))
        print(f"    runtime photo contract: frame {slot + 1} <- {path.name}")

    final_matches = set()
    for photo in selected:
        idx = _approved_match_index(photo, approved_paths)
        if idx is not None:
            final_matches.add(idx)
    if len(final_matches) < target:
        raise SystemExit(
            f"runtime photo contract failed closed: rendered selection has "
            f"{len(final_matches)} approved distinct photos, needs {target}"
        )

    if injected:
        sb.register_photos(injected, "story-runtime-approved")
    print(f"    runtime photo contract: {len(final_matches)} approved photos "
          "will appear in the rendered deck")
    return selected


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

    # The renderer used to be allowed to pass the gate and then hide the very
    # photo pool that justified PASS behind logos and typographic cards. Wrap
    # only this runtime invocation: story_bot keeps its ordinary selector, and
    # the shared contract corrects the final selection before build_frames().
    original_find_all = sb.find_all_photos

    def runtime_find_all(brief):
        selected = original_find_all(brief)
        return _enforce_approved_photo_contract(brief, selected, photos)

    sb.find_all_photos = runtime_find_all
    try:
        sb.main()
    finally:
        sb.find_all_photos = original_find_all


if __name__ == "__main__":
    main()
