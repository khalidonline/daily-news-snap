#!/usr/bin/env python3
"""Runtime-safe Story Bot entrypoint for a personal Snapchat story.

The source inventory only decides whether a story is worth attempting; it does
not set a photo target or ceiling. Reviewed local visuals selected by the
frame's own keywords are trusted, including historical documents, banknotes and
archive scans. The renderer should use every strong relevant visual available,
and the final rendered deck is authoritative for publication quality.

Story visuals are authentic-first: synthetic/generated imagery is disabled for
this runtime. Explicitly reviewed STRONG_CONTEXT real assets may broaden a deck
beyond literal subject matches (for example products, meals, employees,
operations, locations and other documentary context).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
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
    explicitly_relevant,
    runtime_pass,
    runtime_status,
    trusted_selected_local_visual,
)

# Story runtime never creates synthetic visual filler. Insufficient authentic
# coverage stays REVIEW/blocked rather than silently invoking image generation.
os.environ["ALLOW_GENERATED"] = "0"
os.environ["ALLOW_STORY_GENERATION"] = "0"
if hasattr(sb, "ALLOW_GENERATED"):
    sb.ALLOW_GENERATED = False
sb.ALLOW_STORY_GENERATION = False
# The runtime builds a story-specific approved index before story_bot runs.
sb._STORY_RUNTIME_INDEX_SCOPED = True

story_focus.configure(sb)

_AUTHENTIC_VISUAL_PROMPT = r"""

قاعدة التنوع البصري الحقيقي — تنطبق على كل القصص، وبالأخص الشركات والمنتجات:
- استخدم صور حقيقية فقط. لا تستخدم صوراً مولدة أو مشاهد تاريخية مصطنعة
  لتعبئة فراغ بصري؛ إذا لم توجد صورة حقيقية مناسبة، فالأفضل أن تبقى اللقطة
  نصية أو أن تتوقف القصة للمراجعة.
- لا تحوّل قصة الشركة أو العلامة إلى ست صور متشابهة لواجهات الفروع. وسّع
  المشاهد الحقيقية المرتبطة بالبطل: المنتجات، الوجبات والمشروبات، الموظفين
  أثناء العمل، العملاء عندما يكون وجودهم جزءاً من الحدث، العمليات، المطابخ
  والمصانع، الفروع والداخلية، التغليف، المركبات والتوصيل، سلسلة الإمداد،
  الإعلانات والوثائق والأرشيف، والمواقع المرتبطة فعلاً بالقصة.
- التنوع ليس حشواً. اختر من هذه المشاهد فقط عندما يضيف المشهد فهماً جديداً
  للبطل أو لمرحلة حقيقية في رحلته. صورة منتج لا توضع على لقطة نصها عن موقع
  جغرافي مختلف؛ غيّر اللقطة فقط إذا كان المنتج أو الموظف أو العملية نفسها
  جزءاً صحيحاً ومهماً من القصة ومدعوماً بالمصادر.
- إذا كانت أمامك فكرتان صحيحتان ومتقاربتان في الأهمية، فضّل الفكرة التي
  يمكن توثيقها بصورة حقيقية مختلفة عن الصور السابقة: منتج، شخص، عملية،
  مكان، أو أصل أرشيفي. الهدف أن تروي الصور الست القصة أيضاً، لا أن تكرر
  نفس المبنى من زوايا مختلفة.
"""
if "قاعدة التنوع البصري الحقيقي" not in sb.SYSTEM_PROMPT:
    sb.SYSTEM_PROMPT = sb.SYSTEM_PROMPT + _AUTHENTIC_VISUAL_PROMPT

# story_focus normally filters inventory rows by literal subject aliases. That
# is useful on an unscoped catalogue, but Story Runtime replaces IMAGES_INDEX
# with a story-specific approved index first. A second alias filter would hide
# legitimate STRONG_CONTEXT rows such as a meal, employee or factory whose tags
# do not repeat the brand name. Keep filtering everywhere else; trust only the
# already-scoped runtime index here.
_story_inventory_prompt = story_focus.runtime_visual_inventory_prompt


def _scoped_runtime_inventory_prompt(index_path, aliases=()):
    try:
        scoped = Path(index_path).resolve() == Path(nb.IMAGES_INDEX).resolve()
    except Exception:
        scoped = False
    if scoped and getattr(sb, "_STORY_RUNTIME_INDEX_SCOPED", False):
        return _story_inventory_prompt(index_path, aliases=())
    return _story_inventory_prompt(index_path, aliases=aliases)


story_focus.runtime_visual_inventory_prompt = _scoped_runtime_inventory_prompt

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
# A logo may be useful as an accent elsewhere, but it never fills a Story visual slot.
sb.LOGO_MAX_FRAMES = 0


def _editorial_prompt_for_revision():
    inventory = ""
    try:
        # nb.IMAGES_INDEX is already the story-specific, relevance-approved
        # runtime index. Do not filter it a second time by literal aliases.
        inventory = story_focus.runtime_visual_inventory_prompt(nb.IMAGES_INDEX)
    except Exception:
        inventory = ""
    return sb.SYSTEM_PROMPT + inventory


sb.editorial_prompt_for_revision = _editorial_prompt_for_revision
story_editorial_runtime.configure(sb)
city_visual_v3.configure(sb)

# Exact story+frame repairs. These do not broaden global relevance: each pin
# is a previously reviewed local asset assigned to one specific narrative beat.
_CURATED_FRAME_VISUALS = {
    "قصة تأسيس مؤسسة النقد ساما": (
        (("نقود من فضة", "فضة فقط"), "silver-riyal.png"),
        (("ورقة صُنعت لأجل الحجاج", "إيصال الحج"), "first-hajj-receipt.png"),
        (("من إيصال إلى احتياطي",), "sama-history-hq.jpg"),
        (("سعر لا يتحرك", "3.75"), "targeted-riyal-five-faisal-museum.jpg"),
    ),
    "قصة أول مطار في جدة وتطور الطيران المدني": (
        (("الحج كان يأتي من البحر",), "jeddah-port.jpg"),
        (("طائرة واحدة على مدرج تراب",), "saudia-dc3-crowd.jpg"),
        (("نهاية المطار الأول",), "saudia-707-historic.jpg"),
    ),
}


def curated_frame_visual_filename(story, frame):
    blob = " ".join(
        str((frame or {}).get(key, "") or "")
        for key in ("heading", "text", "punch")
    )
    for markers, filename in _CURATED_FRAME_VISUALS.get(str(story or "").strip(), ()):
        if any(marker and marker in blob for marker in markers):
            return filename
    return None


_pre_curated_find_photo = sb.find_photo


def _find_photo_with_curated_frame_pin(
    spec, out_path, seen=(), context="", allow_neutral=True, bank=None
):
    filename = curated_frame_visual_filename(
        sb.STORY, spec if isinstance(spec, dict) else {}
    )
    if filename:
        source = Path("images") / filename
        if source.exists() and source.is_file():
            try:
                digest = sb._photo_digest(source)
                duplicate = any(sb.same_picture(digest, prior) for prior in seen)
            except Exception:
                duplicate = False
            if not duplicate:
                out = Path(out_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, out)
                print(f"      curated frame pin: {filename}")
                return str(out)
            print(f"      curated frame pin already used: {filename}")
    return _pre_curated_find_photo(
        spec, out_path, seen, context,
        allow_neutral=allow_neutral, bank=bank,
    )


sb.find_photo = _find_photo_with_curated_frame_pin


def personal_visual_slots_ready(photos) -> bool:
    """Protect the hook/payoff while allowing one genuine middle-card fallback.

    This function never limits how many visuals may appear. If all six frames
    have strong visuals, all six should be used. Frame 1 and the final frame are
    mandatory visual positions whenever the six-card slot list is known.
    """
    values = list(photos or [])
    if not values:
        return False
    if values[0] is None or values[-1] is None:
        return False
    return sum(1 for photo in values if photo is None) <= 1


# Do not let typographic numbers/dates hide a weak visual deck. The renderer may
# style them nicely, but opening and closing frames still need meaningful visuals
# and at most one middle frame may fall back to text-only.
_personal_find_all_photos = sb.find_all_photos


def _visual_first_find_all_photos(brief):
    photos = _personal_find_all_photos(brief)
    if photos is None:
        return None
    if not personal_visual_slots_ready(photos):
        missing = [i for i, photo in enumerate(photos, 1) if photo is None]
        critical = [i for i in missing if i in {1, len(photos)}]
        if critical:
            reason = "opening/closing frame missing a meaningful visual"
        else:
            reason = "more than one frame missing a meaningful visual"
        sb._LAST_SKIP = (
            f"personal Story visual quality: {reason}; missing frames "
            + ", ".join(str(i) for i in missing)
        )
        print(
            "  ! personal Story visual gate: " + reason
            + " — skipping rather than shipping a weaker deck"
        )
        return None
    return photos


sb.find_all_photos = _visual_first_find_all_photos
story_visual_state.configure(sb)

# Curated documentary assets that belong to a story but use object-focused tags
# in images.txt. Keep this tiny and explicit rather than weakening tag matching.
_STORY_EXTRA_VISUALS = {
    "قصة تأسيس مؤسسة النقد ساما": {
        "first-hajj-receipt.png",
        "rt-sama-1.jpg",
        "silver-riyal.png",
    },
    "قصة أول عملة ورقية سعودية": {
        "targeted-sama-1953-10-riyal.jpg",
        "targeted-sama-1954-5-riyal.jpg",
    },
    "قصة أول مطار في جدة وتطور الطيران المدني": {
        "saudia-dc3-crowd.jpg",
        "saudia-707-historic.jpg",
    },
}


def _matches_story(entry, story, ledger_path=None):
    filename = Path(entry.get("path") or "").name
    if filename and explicitly_relevant(
        filename,
        story,
        ledger_path=ledger_path or Path("images/relevance.json"),
    ):
        return True
    if entry.get("path") and filename in _STORY_EXTRA_VISUALS.get(str(story).strip(), set()):
        return True
    aliases = [a for a in sb.story_aliases(story) if a]
    persons = sb._STORY_PERSONS.get(str(story).strip()) or []
    return story_focus.catalog_tags_match_aliases(
        entry.get("tags", []), aliases + persons
    )


def approved_runtime_visuals(story):
    """Return every distinct approved authentic local visual plus optional logos."""
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
        print(f"    runtime gate: {len(good)} render-eligible stories available in {pool}")
        return story
    return ""


def _filtered_index(story, approved_paths):
    """Write a story-specific image index containing every approved file."""
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
        raise SystemExit("no runtime-PASS story available (needs enough approved source visuals to attempt)")

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
    print("    approved authentic visuals: " + ", ".join(p.name for p in photos))
    if logos:
        print("    optional logo(s): " + ", ".join(p.name for p in logos))
    sb.main()


if __name__ == "__main__":
    main()
