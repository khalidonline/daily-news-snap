"""Subject-cohesion, city wording, and frame-visual policy for Story to Snapchat.

The Story renderer already has strong research, image-source and vision gates.
This layer closes the narrower editorial gaps that surfaced in real decks:

* the subject named by the selected story remains the protagonist throughout;
* a photo is judged against the frame's declared visual target, not every date
  and supporting fact in the prose paragraph;
* city stories prefer photographable beats and do not ship with a mostly
  typographic deck when the frame-specific search failed;
* the writer can see the reviewed runtime visual inventory before choosing
  equally valid story beats, so prose and available evidence can line up;
* city wording explains the subject's own significance before reaching for a
  ranking comparison, and avoids stiff wording such as ``صيرورتها``.

`configure(story_bot)` is intentionally idempotent. Story Runtime calls it once
at import time so the guarded Story-to-Snapchat path always uses the policy.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Iterable


_PROMPT_MARKER = "قاعدة البطل المعلن — تعلو على البناء العام أدناه"
_CONFIGURED_ATTR = "_story_focus_configured"


FOCUS_PROMPT = r"""

قاعدة البطل المعلن — تعلو على البناء العام أدناه:
- موضوع القصة الذي طلبه المستخدم هو بطل القصة من أول لقطة إلى آخر لقطة.
  لا تغيّر البطل لأن البحث كشف كياناً آخر مشهوراً أو معلومة سهلة.
- مجرد أن المعلومة مرتبطة بالبطل ليس كافياً. كل لقطة يجب أن تغيّر فهمنا
  للبطل نفسه: أصله، شكله، تحوّله، نموّه، أثره، أو ما صار إليه.
- كيان مجاور — سفارة، وزارة، شركة، مشروع، شريك، مستثمر، حي، مطار — لا يملك
  لقطة كاملة لمجرد وجوده قرب البطل. إن ذُكر، فالنص يبقى عن التغيير الذي
  أحدثه في البطل نفسه.
- اختبار الحذف: لو حذفت اسم البطل من اللقطة وصارت اللقطة قصة مستقلة عن
  الكيان المجاور، فقد خرجت من القصة. احذفها أو أعد كتابتها حول البطل.
- مثال مدينة الرياض:
  ✗ «تضم الرياض سفارات دول كثيرة...» — هذه لقطة عن السفارات.
  ✓ يجوز ذكر الحي الدبلوماسي فقط إذا كانت اللقطة تشرح، بمصدر موثوق، كيف
    غيّر ذلك عمران الرياض أو امتدادها أو دورها؛ وتبقى الرياض هي الفاعل.

إذا كان بطل القصة مدينة أو مكاناً، فهذه القاعدة تحل محل قالب الشخص:
- لا تُدخل شخصاً كبطل في اللقطة الثانية لمجرد أن البناء العام أدناه يذكر
  شخصاً. المدينة نفسها هي البطل في اللقطات كلها.
- استخدم قوس المدينة: ما كانت عليه → نقطة التحول → التوسع المادي → كيف
  تغيّرت الحياة أو الحركة أو الاقتصاد داخلها → حجمها/دورها اليوم → الحكم
  على ما صارت إليه.
- في قصة الرياض مثلاً: الرياض القديمة وحدودها، ثم ما غيّر المدينة، ثم
  خروجها من حدودها القديمة ونموها، ثم كيف تغيّر شكل الحياة داخلها، ثم
  حجمها ودورها الحديث، ثم حكم واضح على التحول. لا تحوّل أي مرحلة إلى
  قصة عن مؤسسة موجودة في الرياض.
- اختر داخل كل مرحلة لحظة أو مشهداً يمكن توثيقه بصورة حقيقية: سور، شارع،
  حي، مشروع بنية تحتية، وسيلة نقل، أفق المدينة، أو مبنى مذكور فعلاً في
  اللقطة. لا تغيّر القصة من أجل صورة؛ لكن إذا كان لديك خياران صحيحان
  ومتساويان في الأهمية، فضّل المرحلة التي لها شاهد بصري واضح.

قاعدة الصور في قصص المدن والأماكن:
- الصورة تخدم هذه اللقطة تحديداً، لا اسم المدينة عموماً. صورة أفق الرياض
  الحديث لا تصلح تلقائياً للقطة عن الرياض القديمة، وصورة مبنى سفارة لا
  تصلح للقصة لمجرد أنه في الرياض.
- إذا كانت اللقطة تاريخية، فالصورة يجب أن توافق المكان والحقبة قدر الإمكان.
  صورة حديثة لمشهد قديم مرفوضة إذا أوحت للقارئ بأنها تمثل تلك المرحلة.
- image_keywords في قصة مدينة هي «الهدف البصري» للّقطة: أسماء المشهد
  المادي الذي تريد أن يراه القارئ، لا ملخص الفقرة كلها. قد تذكر الفقرة
  1902 و2024 للمقارنة، بينما الهدف البصري هو «Riyadh Metro» أو «Riyadh
  skyline»؛ عندها الصورة الحديثة صحيحة ولا تُرفض بسبب سنة 1902 الواردة
  كخلفية سردية.
- تبدأ image_keywords من المدينة/المكان المعلن ثم الشيء المادي أو المرحلة
  التي تتحدث عنها اللقطة؛ لا تستبدل المدينة بكيان مجاور جذاب بصرياً.
- اجعل لكل لقطة هدفاً بصرياً مختلفاً قدر الإمكان حتى تحكي الصور الرحلة
  نفسها: قديم → توسع → بنية تحتية/حياة → مدينة حديثة، لا ست صور متشابهة.

قاعدة اللغة والمقارنة في قصص المدن:
- الأصل أن تذكر رقم المدينة نفسه ثم تشرح ماذا يكشف عن حجمها أو نشاطها أو
  دورها. المقارنة ليست مطلوبة لمجرد إثبات أن الرقم كبير.
- لا تقل «أعلى من أي مدينة سعودية أخرى»، ولا تجعل «الأولى» أو «تتفوق على»
  هي الخلاصة؛ هذه صياغة منافسة لا نحتاجها عندما تكفي دلالة الرقم نفسه.
- إذا كانت المقارنة ضرورية للفهم ومبنية على نفس القائمة والسنة والمقياس،
  فاجعلها سياقاً محايداً لا سباقاً. مثال مقبول: «أكثر من ثاني مدينة في
  القائمة»، ثم عد فوراً إلى ما يعنيه الرقم للمدينة نفسها.
- استخدم العربية الطبيعية: «تحولها»، «ما أصبحت عليه»، «ما وصلت إليه».
  لا تستخدم «صيرورتها» أو «صيرورة المدينة» في النص الموجّه لسناب شات.
- نموذج ختام للرياض — أسلوبي فقط، ولا تستخدم رقمه إلا إذا أثبته البحث
  لنفس السنة والمقياس:
  heading: «من بلدة مسوّرة إلى مدينة بهذا الحجم»
  text: «في 2024 سجّلت الرياض 225 مليار ريال في مبيعات نقاط البيع. رقم
  يعكس حجم السوق والحركة الاقتصادية في مدينة كانت قبل نحو قرن محصورة داخل
  سور من الطين.»
  punch: «هذا هو حجم التحول الذي عاشته الرياض.»
"""


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(v.strip() for v in values if str(v).strip()))


def _subject_names(story: str, aliases_fn: Callable[[str], Iterable[str]]) -> list[str]:
    aliases = _unique(aliases_fn(story) or [])
    if aliases:
        return aliases
    head = str(story or "").split("|", 1)[0].split(":", 1)[0].strip()
    if head.startswith("قصة "):
        head = head[4:].strip()
    return [head] if head else []


def story_focus_contract(
    story: str,
    aliases_fn: Callable[[str], Iterable[str]],
) -> str:
    """Human-readable contract that keeps the selected subject in ownership."""
    names = _subject_names(story, aliases_fn)
    label = " / ".join(names[:4]) or str(story or "").strip()
    return (
        f"البطل المعلن: {label}.\n"
        "ثبّت هذا البطل في اللقطات كلها. العلاقة وحدها ليست كافية: كل "
        "لقطة يجب أن تصف مرحلة أو تغيراً أو صفة في البطل نفسه، لا أن تتحول "
        "إلى قصة عن كيان مجاور.\n"
        "مثال: مجرد معلومة مثل «السفارات في الرياض» ليست كافية لتصبح لقطة "
        "في قصة الرياض؛ لا تُذكر إلا إذا شرحت تحولاً في الرياض نفسها.\n"
        "اختبار قبل التسليم: إذا أمكن حذف اسم البطل وبقيت اللقطة قصة مستقلة "
        "عن سفارة أو شركة أو وزارة أو مشروع، فأعد كتابة اللقطة أو احذفها."
    )


def _renderer_frame_text(frame: dict) -> str:
    heading = str(frame.get("heading", "") or "").strip()
    text = str(frame.get("text", "") or "").strip()
    return "\n".join(v for v in (heading, text) if v).strip()


def _norm_context(value: str) -> str:
    return " ".join(str(value or "").split())


def frame_from_renderer_context(frames: Iterable[dict], context: str):
    """Recover the model frame from story_bot's ``heading + text`` context.

    Company stories may prefix the renderer context with a subject sentence,
    so suffix matching is deliberate after whitespace normalization.
    """
    needle = _norm_context(context)
    if not needle:
        return None
    for frame in frames or []:
        frame_text = _norm_context(_renderer_frame_text(frame))
        if frame_text and (needle == frame_text or needle.endswith(frame_text)):
            return frame
    return None


def _frame_visual_targets(frame: dict) -> list[str]:
    return _unique(
        list(frame.get("image_keywords") or [])
        + list(frame.get("image_keywords_ar") or [])
    )


def frame_visual_context(
    story: str,
    frame: dict,
    aliases_fn: Callable[[str], Iterable[str]],
) -> str:
    """Vision context bound to the subject and the frame's visual target.

    If the model supplied image keywords, they are the authoritative visual
    target. Supporting dates in the prose are narrative background and must not
    accidentally turn a current-scene image into an anachronism. Legacy frames
    without image keywords retain the older heading+text fallback.
    """
    names = _subject_names(story, aliases_fn)
    label = " / ".join(names[:4]) or str(story or "").strip()
    heading = str(frame.get("heading", "") or "").strip()
    targets = _frame_visual_targets(frame)

    if targets:
        target_text = " / ".join(targets[:8])
        body = "\n".join(v for v in (heading, f"الهدف البصري: {target_text}") if v)
        target_rule = (
            "احكم على الصورة مقابل الهدف البصري المكتوب أدناه. لا تجعل سنة "
            "أو معلومة وردت كخلفية في نص اللقطة شرطاً زمنياً للصورة ما لم "
            "تكن السنة أو الحقبة جزءاً من الهدف البصري نفسه. "
        )
    else:
        body = _renderer_frame_text(frame)
        target_rule = ""

    return (
        f"القصة كلها عن: {label}.\n"
        "راجع الصورة لهذه اللقطة تحديداً، لا لموضوع القصة عموماً. يجب أن "
        "تُظهر مباشرةً المكان/الشخص/الشيء أو المرحلة التي تصفها اللقطة، "
        "وأن تبقى ضمن بطل القصة المعلن. مجرد ارتباط الصورة بالبطل ليس كافياً. "
        f"{target_rule}"
        "إذا كان الهدف البصري نفسه تاريخياً فطابق الحقبة أيضاً؛ صورة حديثة "
        "لا تمثل مرحلة قديمة لمجرد أنها للمكان نفسه.\n"
        f"{body}"
    ).strip()


def polish_city_wording(text: str) -> str:
    """Remove the two city-language regressions seen in the Riyadh deck."""
    value = str(text or "")
    value = value.replace("صيرورتها", "تحولها")
    value = value.replace("صيرورته", "تحوله")
    value = value.replace("صيرورة المدينة", "تحول المدينة")
    value = value.replace("صيرورة", "تحول")

    # Remove the hard-ranking clause and, when present, the immediate named
    # runner-up comparison that turns the city card into a competition table.
    # The prompt still permits a neutral "more than the second city" context
    # when the model determines that comparison is genuinely useful.
    value = re.sub(
        r"(?:[—–-]\s*)?أعلى من أي مدينة سعودية أخرى"
        r"(?:،\s*ومقابل[^.؟!]+)?",
        "رقم يوضح حجم النشاط الاقتصادي في المدينة",
        value,
    )
    return value


def _is_city_brief(brief: dict) -> bool:
    frames = list((brief or {}).get("frames") or [])
    if not frames:
        return False
    city_frames = sum(
        1 for frame in frames
        if str(frame.get("subject_kind", "")).strip() == "place_city"
    )
    return city_frames >= max(2, (len(frames) + 1) // 2)


def runtime_visual_inventory_prompt(index_path) -> str:
    """Describe the already-reviewed runtime images to the story writer.

    The filtered runtime index is evidence availability, not a factual source.
    It helps the writer prefer an equally important, photographable beat while
    all factual claims still have to come from researched sources.
    """
    path = Path(index_path) if index_path else None
    if path is None:
        return ""
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    rows = []
    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if not parts or not parts[0]:
            continue
        filename = parts[0]
        tags = parts[1] if len(parts) > 1 else ""
        rows.append(f"- {filename}: {tags}" if tags else f"- {filename}")

    if not rows:
        return ""

    return (
        "\n\nصور محلية مراجعة ومتاحة فعلاً لهذه القصة:\n"
        + "\n".join(rows)
        + "\n"
        "- هذه الصور ليست مصادر للحقائق. أثبت كل معلومة من البحث والمصادر، "
        "ولا تستنتج حدثاً أو تاريخاً من اسم الملف.\n"
        "- لا تغيّر القصة لتخدم صورة. لكن إذا كان أمامك مرحلتان صحيحتان "
        "ومتقاربتان في الأهمية، فضّل مرحلة مهمة يمكن أن يرويها واحد من هذه "
        "الصور بوضوح.\n"
        "- في قصص المدن، حاول أن تتوافق أربع لقطات على الأقل مع صور مراجعة "
        "مختلفة أو مع مشاهد مباشرة يسهل العثور عليها؛ لا تُدخل كياناً مجاوراً "
        "لمجرد أن له صورة.\n"
        "- إذا كانت صورة محلية مناسبة للّقطة، ضع الاسم/الوسم الدال عليها في "
        "image_keywords و image_keywords_ar حتى يستطيع محرك الصور العثور عليها."
    )


def prepare_city_visual_search(brief: dict) -> dict:
    """Let the local library see Arabic city tags as well as English targets."""
    if not isinstance(brief, dict) or not _is_city_brief(brief):
        return brief
    for frame in brief.get("frames") or []:
        english = list(frame.get("image_keywords") or [])
        arabic = list(frame.get("image_keywords_ar") or [])
        frame["image_keywords"] = _unique(english + arabic)
    return brief


def city_deck_visuals_ready(brief: dict, photos: Iterable[object]) -> bool:
    """City decks need four matched visual slots; non-city decks are unchanged."""
    if not _is_city_brief(brief):
        return True
    frames = list((brief or {}).get("frames") or [])
    required = min(4, len(frames))
    matched = sum(1 for photo in (photos or []) if photo is not None)
    return matched >= required


def _polish_brief_city_language(brief: dict) -> dict:
    if not isinstance(brief, dict) or not _is_city_brief(brief):
        return brief
    for frame in brief.get("frames") or []:
        for key in ("heading", "text", "punch"):
            if key in frame:
                frame[key] = polish_city_wording(frame.get(key, ""))
    if "caption" in brief:
        brief["caption"] = polish_city_wording(brief.get("caption", ""))
    return brief


def story_photo_verdict_ok(verdict: str) -> bool:
    """Story photos require a positive vision verdict; neutral is not enough."""
    return str(verdict or "").strip().lower() == "yes"


def configure(story_bot_module):
    """Apply subject focus to an imported ``story_bot`` module once."""
    sb = story_bot_module
    if getattr(sb, _CONFIGURED_ATTR, False):
        return sb

    # Make the helpers visible on story_bot too: operations/tests can inspect
    # the active contract without knowing about this policy module.
    sb.story_focus_contract = lambda story: story_focus_contract(
        story, sb.story_aliases
    )
    sb.frame_visual_context = lambda story, frame: frame_visual_context(
        story, frame, sb.story_aliases
    )
    sb.story_photo_verdict_ok = story_photo_verdict_ok

    if _PROMPT_MARKER not in sb.SYSTEM_PROMPT:
        # Put the rule before the existing generic person/company structure so
        # its explicit "city overrides person template" instruction wins.
        anchor = "\nالبناء:\n"
        if anchor in sb.SYSTEM_PROMPT:
            sb.SYSTEM_PROMPT = sb.SYSTEM_PROMPT.replace(
                anchor, FOCUS_PROMPT + anchor, 1
            )
        else:
            sb.SYSTEM_PROMPT = FOCUS_PROMPT.lstrip() + "\n" + sb.SYSTEM_PROMPT

    original_photo_shows = sb.photo_shows
    original_find_all_photos = sb.find_all_photos
    original_research = sb.research
    active = {"story": "", "frames": []}

    def strict_story_photo_shows(photo, context):
        story = active["story"]
        if not story:
            # Outside the frame-selection phase keep the underlying behavior;
            # portrait prechecks and unrelated utilities are not broadened or
            # tightened by this Story-only rule.
            return original_photo_shows(photo, context)

        frame = frame_from_renderer_context(active["frames"], str(context or ""))
        if frame is None:
            frame = {"heading": "", "text": str(context or "")}
        contract = frame_visual_context(story, frame, sb.story_aliases)
        verdict = original_photo_shows(photo, contract)
        if story_photo_verdict_ok(verdict):
            return "yes"

        # Existing Story code knows how to continue searching after "no".
        # Mapping neutral -> no closes both historical-neutral banking and the
        # local-library shortcut that previously accepted a related picture.
        print(
            "      (frame relevance gate: photo is not a confirmed match "
            "for this frame — rejected)"
        )
        return "no"

    def focused_research(story):
        # Story Runtime replaces news_bot.IMAGES_INDEX with a story-specific
        # index containing only approved local files before sb.main() starts.
        # Reading it here gives the writer the exact visual inventory that the
        # renderer will later be allowed to use.
        inventory = ""
        try:
            import news_bot as nb

            inventory = runtime_visual_inventory_prompt(nb.IMAGES_INDEX)
        except Exception:
            inventory = ""

        previous_prompt = sb.SYSTEM_PROMPT
        if inventory:
            sb.SYSTEM_PROMPT = previous_prompt + inventory
            print("    writer visual inventory: reviewed local anchors supplied")
        try:
            brief = original_research(story)
        finally:
            sb.SYSTEM_PROMPT = previous_prompt

        brief = _polish_brief_city_language(brief)
        return prepare_city_visual_search(brief)

    def focused_find_all_photos(brief):
        previous_story = active["story"]
        previous_frames = active["frames"]
        active["story"] = str((brief or {}).get("story", "") or "").strip()
        active["frames"] = list((brief or {}).get("frames") or [])
        try:
            photos = original_find_all_photos(brief)
            if photos is not None and not city_deck_visuals_ready(brief, photos):
                matched = sum(1 for photo in photos if photo is not None)
                required = min(4, len((brief or {}).get("frames") or []))
                sb._LAST_SKIP = (
                    f"frame-aware city visual gate: {matched}/{required} "
                    "matched visual slots"
                )
                print(
                    f"  ! city visual gate: only {matched} matched frame "
                    f"visuals; need {required} — skipping rather than "
                    "shipping a mostly text-only city deck"
                )
                return None
            return photos
        finally:
            active["story"] = previous_story
            active["frames"] = previous_frames

    sb.photo_shows = strict_story_photo_shows
    sb.research = focused_research
    sb.find_all_photos = focused_find_all_photos
    setattr(sb, _CONFIGURED_ATTR, True)
    return sb
