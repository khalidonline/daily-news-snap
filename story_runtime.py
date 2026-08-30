#!/usr/bin/env python3
"""Runtime-safe Story Bot entrypoint for a personal Snapchat story.

The runtime inventory is a useful starting filter, not a corporate asset gate:
four distinct reviewed relevant visuals are enough to attempt a story and a
logo is optional. Reviewed local visuals selected by the frame's own keywords
are trusted, including historical documents, banknotes and archive scans.
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
from runtime_relevance import (
    asset_countable,
    runtime_pass,
    runtime_status,
    trusted_selected_local_visual,
)

story_focus.configure(sb)

PERSONAL_SNAP_PROMPT = """

قاعدة سناب شخصي — البساطة أهم من أسلوب التقارير:
- هذا سناب شخصي لجمهور يتابع قصة ممتعة، وليس تقرير شركة أو عرضاً تنفيذياً.
- اجعل نص كل لقطة قصيراً وسريع القراءة: فكرة واحدة واضحة، بلا حشو ولا لغة مؤسسية.
- الصورة هي جزء من السرد، وليست زينة. اختر شيئاً يراه القارئ ويفهم منه المرحلة فوراً.
- الصورة الصحيحة قد تكون صورة فوتوغرافية، وثيقة أصلية، ورقة نقدية، إيصالاً، إعلاناً قديماً، خريطة تاريخية أو مسحاً أرشيفياً إذا كان هذا الشيء نفسه جزءاً من القصة.
- لا تستخدم شعاراً لمجرد ملء الفراغ. الشعار اختياري ويظهر عند الحاجة فقط.
- إذا لم تجد صورة مناسبة فعلاً، لا تختلق صلة ضعيفة. لقطة نصية واحدة مقبولة كحد أقصى في القصة كلها.
"""
if "قاعدة سناب شخصي" not in sb.SYSTEM_PROMPT:
    sb.SYSTEM_PROMPT += PERSONAL_SNAP_PROMPT

# The reviewed local library is already selected by the frame's image keywords.
# For Story-to-Snapchat, trust that curation instead of making a generic vision
# model veto a banknote/document merely because it is not a conventional photo.
_story_photo_shows = sb.photo_shows


def _personal_story_photo_shows(photo, context):
    story = str(sb.STORY or "").strip()
    if story and trusted_selected_local_visual(photo, story):
        print("      reviewed local visual trusted for personal Story")
        return "yes"
    return _story_photo_shows(photo, context)


sb.photo_shows = _personal_story_photo_shows
# Keep logos as occasional accents, not corporate wallpaper.
sb.LOGO_MAX_FRAMES = min(1, int(getattr(sb, "LOGO_MAX_FRAMES", 1) or 1))


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


def personal_visual_slots_ready(photos) -> bool:
    """A six-card personal Story may have at most one genuinely empty visual slot."""
    values = list(photos or [])
    if not values:
        return False
    return sum(1 for photo in values if photo is None) <= 1


# Do not let typographic numbers/dates hide a mostly empty deck. The legacy
# renderer may style them nicely, but they are still not photos/documents.
_personal_find_all_photos = sb.find_all_photos


def _visual_first_find_all_photos(brief):
    photos = _personal_find_all_photos(brief)
    if photos is None:
        return None
    if not personal_visual_slots_ready(photos):
        missing = [i for i, photo in enumerate(photos, 1) if photo is None]
        sb._LAST_SKIP = (
            "personal Story visual coverage: missing real visuals on frames "
            + ", ".join(str(i) for i in missing)
        )
        print(
            "  ! personal Story visual gate: more than one frame has no real "
            "visual — skipping rather than shipping a text-heavy deck"
        )
        return None
    return photos


sb.find_all_photos = _visual_first_find_all_photos
story_visual_state.configure(sb)


def _matches_story(entry, story):
    aliases = [a for a in sb.story_aliases(story) if a]
    persons = sb._STORY_PERSONS.get(str(story).strip()) or []
    return story_focus.catalog_tags_match_aliases(
        entry.get("tags", []), aliases + persons
    )


def approved_runtime_visuals(story):
    """Return distinct approved local visuals plus optional local logos."""
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

    _, logos = sb.resolve_runtime_visuals(story)
    return kept, logos


def coverage(story):
    photos, logos = approved_runtime_visuals(story)
    return photos, logos, runtime_status(len(photos), len(logos))


def _eligible_story(story):
    photos, logos, status = coverage(story)
    print(f"    runtime relevance: {status} "
          f"({len(photos)} approved visual(s), {len(logos)} optional logo(s))")
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
        raise SystemExit("no runtime-PASS story available (needs 4 approved visuals)")

    photos, logos, status = coverage(story)
    if not runtime_pass(len(photos), len(logos)):
        raise SystemExit(
            f"story blocked by runtime relevance gate: {status}; "
            f"{len(photos)} approved visual(s): {story}")

    filtered = _filtered_index(story, photos)
    nb.IMAGES_INDEX = filtered
    os.environ["IMAGES_INDEX"] = str(filtered)
    sb.STORY = story
    if (os.getenv("STORY_SUPPRESS_TELEGRAM") or "").strip() == "1":
        sb.notify = lambda *args, **kwargs: None
        sb.notify_album = lambda *args, **kwargs: None
        print("    intermediate Telegram notifications suppressed")
    print(f"    runtime gate PASS: {story}")
    print("    approved visuals: " + ", ".join(p.name for p in photos))
    if logos:
        print("    optional logo(s): " + ", ".join(p.name for p in logos))
    sb.main()


if __name__ == "__main__":
    main()
