"""Simple, deterministic visual selection for city stories.

City stories use a small ladder:
1. reviewed local photo that exactly matches the frame's visible beat;
2. reviewed local photo that is clearly of the declared city;
3. a short generic city web search only while fewer than four photos exist;
4. designed text card.

The layer is intentionally separate from the generic Story Bot image ladder so
company/person stories keep their stricter identity behavior unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import story_focus


_CONFIGURED_ATTR = "_city_visual_fallback_configured"

CITY_PROMPT = r"""

قاعدة مبسطة لصور قصص المدن — تطبق بعد قواعد تماسك القصة:
- ابدأ بالصورة المحلية المراجعة التي تطابق مشهد اللقطة فعلاً. إذا كانت
  الفهرسة المراجعة تثبت المكان/الحدث/السنة المناسبة، فلا تطلب من نموذج
  الرؤية إعادة تخمين هذه البيانات من شكل الصورة.
- إذا لم توجد صورة دقيقة، استخدم صورة حقيقية واضحة للمدينة نفسها: أفق، شارع،
  معلم، مطار، ملعب، مبنى، حي أو مساحة عامة. لا يلزم أن تثبت الصورة كل جملة
  في النص؛ يكفي أن تكون للمدينة المعلنة وألا توحي بحدث أو مكان آخر.
- لا تستخدم صورة يذكر عنوانها أو وصفها مدينة أخرى. جدة لا تصلح لقصة الرياض،
  حتى لو بدت الصورة خليجية أو سعودية.
- لا تغيّر وقائع القصة لتخدم الصورة، ولا تنقل كلمات بحث من لقطة سابقة إلى
  لقطة لاحقة. البحث العام للمدينة يكون باسم المدينة ومشاهدها العامة فقط.
- بمجرد تأمين أربع صور جيدة للمدينة، لا تبدأ بحثاً شبكياً مكلفاً فقط لملء
  بقية اللقطات. الصورة المحلية المناسبة ما زالت مسموحة، وإلا فالتصميم النصي
  أفضل من بحث طويل أو صورة ضعيفة.
- في ختام قصة الرياض لا تستخدم حصة أسبوعية أو نسبة ترتيبية مثل 34% إذا كان
  متاحاً رقم سنوي للرياض نفسها على نفس المقياس. فضّل رقم سنوي يشرح حجم
  النشاط ثم اربطه ببداية القصة وبالتحول الذي عاشته المدينة.
- نموذج الخاتمة الأسلوبي: «في 2024 سجّلت الرياض 225 مليار ريال في مبيعات
  نقاط البيع. رقم يعكس حجم السوق والحركة الاقتصادية في مدينة كانت قبل نحو
  قرن محصورة داخل سور من الطين.» ثم: «هذا هو حجم التحول الذي عاشته الرياض.»
  لا تستخدم الرقم نفسه إلا إذا أثبته البحث لنفس السنة والمقياس.
"""


_CITY_NAME_GROUPS = (
    ("riyadh", "الرياض"),
    ("jeddah", "جدة"),
    ("makkah", "mecca", "مكة"),
    ("madinah", "medina", "المدينة المنورة"),
    ("dammam", "الدمام"),
    ("khobar", "al khobar", "الخبر"),
    ("dhahran", "الظهران"),
    ("taif", "الطائف"),
    ("abha", "أبها"),
    ("tabuk", "تبوك"),
    ("buraidah", "بريدة"),
    ("hail", "حائل"),
    ("jubail", "الجبيل"),
    ("yanbu", "ينبع"),
)

_VISUAL_CLUE_STOP = {
    "riyadh", "الرياض", "saudi", "saudiarabia", "السعودية",
    "city", "مدينة", "photo", "صورة", "old", "القديم", "القديمة",
    "modern", "حديث", "الحديث", "historical", "تاريخي", "تاريخية",
    "train", "قطار", "station", "محطة", "year", "سنة",
}


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))


def _read_visual_index(index_path) -> list[dict]:
    path = Path(index_path) if index_path else None
    if path is None:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if not parts or not parts[0]:
            continue
        rows.append({
            "filename": parts[0],
            "tags": parts[1] if len(parts) > 1 else "",
            "credit": parts[2] if len(parts) > 2 else "",
        })
    return rows


def _source_name(photo) -> str:
    path = Path(str(photo or ""))
    marker = Path(str(path) + ".exempt")
    if marker.exists():
        try:
            value = marker.read_text(encoding="utf-8").strip()
            if ":" in value:
                marked = value.split(":", 1)[1].strip()
                if marked:
                    return Path(marked).name
        except OSError:
            pass
    return path.name


def _word_tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9]+|[ء-ي]+", str(text or ""))
        if len(token) > 2
    }


def _visual_clues(values: Iterable[str], aliases: Iterable[str]) -> set[str]:
    alias_tokens = set()
    for alias in aliases or []:
        alias_tokens |= _word_tokens(alias)
    tokens = set()
    for value in values or []:
        tokens |= _word_tokens(value)
    return tokens - alias_tokens - _VISUAL_CLUE_STOP


def exact_city_keywords(frame: dict, aliases: Iterable[str]) -> list[str]:
    """Frame targets for the exact rung, without bare city fallbacks."""
    aliases_cf = {str(a).strip().casefold() for a in aliases or [] if str(a).strip()}
    values = list(frame.get("image_keywords") or []) + list(
        frame.get("image_keywords_ar") or []
    )
    return _unique(v for v in values if str(v).strip().casefold() not in aliases_cf)[:6]


def reviewed_city_exact_match(
    photo,
    frame: dict,
    index_path,
    aliases: Iterable[str] = (),
) -> bool:
    """Trust a reviewed city file when its catalogue matches this beat."""
    source = _source_name(photo)
    row = next(
        (r for r in _read_visual_index(index_path)
         if Path(r["filename"]).name == source),
        None,
    )
    if row is None:
        return False
    metadata = " ".join([source, row.get("tags", ""), row.get("credit", "")])
    if not story_focus.catalog_tags_match_aliases([metadata], aliases):
        return False

    target_text = " ".join(exact_city_keywords(frame, aliases))
    target_years = set(re.findall(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)", target_text))
    meta_years = set(re.findall(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)", metadata))
    if target_years and meta_years and target_years & meta_years:
        return True

    target_cf = target_text.casefold()
    if ("1970s" in target_cf or "السبعينات" in target_cf) and any(
        y.startswith("197") for y in meta_years
    ):
        return True

    target_clues = _visual_clues(exact_city_keywords(frame, aliases), aliases)
    meta_clues = _visual_clues([metadata], aliases)
    return bool(target_clues & meta_clues)


def city_fallback_queries(aliases: Iterable[str]) -> list[str]:
    """Short generic city-only fallback list; never inherits frame history."""
    aliases = _unique(aliases)
    latin = next((a for a in aliases if a.isascii()), "")
    arabic = next((a for a in aliases if not a.isascii()), "")
    if latin:
        queries = [
            f"{latin} skyline",
            f"{latin} street",
            f"{latin} landmark",
            f"{latin} airport",
            f"{latin} stadium",
            f"مطار {arabic}" if arabic else f"{latin} public space",
        ]
    elif arabic:
        queries = [
            f"أفق {arabic}",
            f"شارع في {arabic}",
            f"معلم {arabic}",
            f"مطار {arabic}",
            f"ملعب {arabic}",
            f"مساحة عامة في {arabic}",
        ]
    else:
        queries = []
    return _unique(queries)[:6]


def _declared_city_group(aliases: Iterable[str]):
    aliases_cf = {str(a).strip().casefold() for a in aliases or [] if str(a).strip()}
    for group in _CITY_NAME_GROUPS:
        if aliases_cf & {name.casefold() for name in group}:
            return group
    return tuple(aliases_cf)


def city_candidate_metadata_ok(metadata: str, aliases: Iterable[str]) -> bool:
    """Reject metadata explicitly naming another known city."""
    text = str(metadata or "").casefold()
    declared = {name.casefold() for name in _declared_city_group(aliases)}
    for group in _CITY_NAME_GROUPS:
        group_cf = {name.casefold() for name in group}
        if group_cf & declared:
            continue
        for name in group_cf:
            if any("ء" <= ch <= "ي" for ch in name):
                if name in text:
                    return False
            elif re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text):
                return False
    return True


def city_fallback_visual_context(story: str, aliases: Iterable[str]) -> str:
    label = " / ".join(_unique(aliases)[:4]) or str(story or "").strip()
    return (
        f"هذه صورة احتياطية لقصة عن المدينة: {label}.\n"
        "اقبل فقط صورة حقيقية واضحة للمدينة نفسها أو لمعلم/شارع/مطار/ملعب/"
        "حي/مساحة عامة أو حياة حضرية فيها. لا يلزم أن تثبت الصورة الحدث أو "
        "السنة المذكورة في نص اللقطة؛ هي صورة سياقية للمدينة فقط. ارفض إذا "
        "ظهر أنها لمدينة أخرى أو إذا لم يمكن تأكيد ارتباطها بالمدينة المعلنة."
    )


def _is_city_frame(frame: dict) -> bool:
    return str((frame or {}).get("subject_kind", "")).strip() == "place_city"


def _frame_text(frame: dict) -> str:
    return "\n".join(
        v for v in (
            str(frame.get("heading", "") or "").strip(),
            str(frame.get("text", "") or "").strip(),
        ) if v
    )


def _norm(value: str) -> str:
    return " ".join(str(value or "").split())


def _frame_from_context(frames: Iterable[dict], context: str):
    needle = _norm(context)
    for frame in frames or []:
        value = _norm(_frame_text(frame))
        if value and (needle == value or needle.endswith(value)):
            return frame
    return None


def configure(story_bot_module):
    """Install the simple city-only selector after story_focus.configure()."""
    sb = story_bot_module
    if getattr(sb, _CONFIGURED_ATTR, False):
        return sb

    base_find_photo = sb.find_photo
    base_find_all_photos = sb.find_all_photos
    base_research = sb.research
    active = {
        "story": "",
        "frames": [],
        "aliases": [],
        "attempted": set(),
        "photo_count": 0,
    }

    def index_path():
        try:
            import news_bot as nb
            return nb.IMAGES_INDEX
        except Exception:
            return None

    def reviewed_rows():
        return _read_visual_index(index_path())

    def fresh(photo, seen):
        if not photo:
            return False
        try:
            digest = sb._photo_digest(photo)
            return not any(sb.same_picture(digest, prior) for prior in seen)
        except Exception:
            return True

    def reserved_for_other_frames(frame):
        path = index_path()
        if not path:
            return set()
        reserved = set()
        for row in _read_visual_index(path):
            candidate = Path(row["filename"])
            for other in active["frames"]:
                if other is frame or not _is_city_frame(other):
                    continue
                if reviewed_city_exact_match(
                    candidate, other, path, aliases=active["aliases"]
                ):
                    reserved.add(Path(row["filename"]).name)
                    break
        return reserved

    def exact_local(frame, out_path, seen, lib_exclude=()):
        path = index_path()
        if not path:
            return None
        keywords = exact_city_keywords(frame, active["aliases"])
        if not keywords:
            return None
        tried = list(lib_exclude or [])
        for _ in range(6):
            cand, _credit = sb.fetch_local_photo(
                [], keywords, out_path,
                exclude=tried,
                respect_cooldown=False,
            )
            if not cand:
                break
            source = _source_name(cand)
            if not fresh(cand, seen):
                tried.append(source)
                continue
            if reviewed_city_exact_match(
                cand, frame, path, aliases=active["aliases"]
            ):
                print(
                    f"      city exact local: {source} "
                    "(reviewed metadata; cooldown ignored)"
                )
                return cand
            tried.append(source)
        return None

    def generic_local(frame, out_path, seen, lib_exclude=()):
        path = index_path()
        if not path:
            return None
        rows = _read_visual_index(path)
        by_name = {Path(r["filename"]).name: r for r in rows}
        reserved = reserved_for_other_frames(frame)
        tried = list(dict.fromkeys(list(lib_exclude or []) + list(reserved)))
        for query in city_fallback_queries(active["aliases"]):
            cand, _credit = sb.fetch_local_photo(
                [], [query], out_path,
                exclude=tried,
                respect_cooldown=False,
            )
            if not cand:
                continue
            source = _source_name(cand)
            row = by_name.get(source)
            metadata = " ".join([
                source,
                row.get("tags", "") if row else "",
                row.get("credit", "") if row else "",
            ])
            if source in reserved or row is None:
                tried.append(source)
                continue
            if not story_focus.catalog_tags_match_aliases(
                [metadata], active["aliases"]
            ):
                tried.append(source)
                continue
            if not city_candidate_metadata_ok(metadata, active["aliases"]):
                tried.append(source)
                continue
            if not fresh(cand, seen):
                tried.append(source)
                continue
            print(
                f"      city fallback local: {source} "
                "(reviewed city identity; cooldown ignored)"
            )
            return cand
        return None

    def web_fallback(out_path, seen):
        if active["photo_count"] >= 4:
            return None
        queries = city_fallback_queries(active["aliases"])
        if not queries:
            return None
        local_names = [Path(r["filename"]).name for r in reviewed_rows()]
        spec = {
            "image_keywords": queries[:4],
            "image_keywords_ar": [],
            "lib_exclude": local_names,
        }
        return base_find_photo(
            spec,
            out_path,
            seen,
            city_fallback_visual_context(active["story"], active["aliases"]),
            allow_neutral=False,
        )

    def focused_find_photo(spec, out_path, seen=(), context="", allow_neutral=True,
                           bank=None):
        frame = _frame_from_context(active["frames"], context)
        if (not active["story"] or frame is None or not _is_city_frame(frame)):
            return base_find_photo(
                spec, out_path, seen, context,
                allow_neutral=allow_neutral, bank=bank,
            )

        key = id(frame)
        if key in active["attempted"]:
            return None
        active["attempted"].add(key)

        excludes = (spec or {}).get("lib_exclude") or []
        photo = exact_local(frame, out_path, seen, excludes)
        if photo is None:
            photo = generic_local(frame, out_path, seen, excludes)
        if photo is None:
            photo = web_fallback(out_path, seen)
        if photo is not None:
            active["photo_count"] += 1
        return photo

    def focused_research(story):
        previous = sb.SYSTEM_PROMPT
        sb.SYSTEM_PROMPT = previous + CITY_PROMPT
        try:
            return base_research(story)
        finally:
            sb.SYSTEM_PROMPT = previous

    def focused_find_all_photos(brief):
        previous = dict(active)
        active["story"] = str((brief or {}).get("story", "") or "").strip()
        active["frames"] = list((brief or {}).get("frames") or [])
        active["aliases"] = _unique(sb.story_aliases(active["story"]))
        active["attempted"] = set()
        active["photo_count"] = 0
        try:
            return base_find_all_photos(brief)
        finally:
            active.clear()
            active.update(previous)

    sb.find_photo = focused_find_photo
    sb.research = focused_research
    sb.find_all_photos = focused_find_all_photos
    setattr(sb, _CONFIGURED_ATTR, True)
    return sb
