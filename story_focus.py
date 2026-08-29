"""Subject-cohesion and frame-visual policy for Story to Snapchat.

The Story renderer already has strong research, image-source and vision gates.
This layer closes two narrower editorial gaps without duplicating that system:

* the subject named by the selected story remains the protagonist throughout;
* during Story rendering, a photo must be a confirmed match for the specific
  frame as well as the declared story subject. A merely related/neutral photo
  is rejected and the existing renderer falls through to another source or to
  its designed text-only treatment.

`configure(story_bot)` is intentionally idempotent. Story Runtime calls it once
at import time so the guarded Story-to-Snapchat path always uses the policy.
"""

from __future__ import annotations

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

قاعدة الصور في قصص المدن والأماكن:
- الصورة تخدم هذه اللقطة تحديداً، لا اسم المدينة عموماً. صورة أفق الرياض
  الحديث لا تصلح تلقائياً للقطة عن الرياض القديمة، وصورة مبنى سفارة لا
  تصلح للقصة لمجرد أنه في الرياض.
- إذا كانت اللقطة تاريخية، فالصورة يجب أن توافق المكان والحقبة قدر الإمكان.
  صورة حديثة لمشهد قديم مرفوضة إذا أوحت للقارئ بأنها تمثل تلك المرحلة.
- image_keywords في قصة مدينة تبدأ من المدينة/المكان المعلن ثم الشيء المادي
  أو المرحلة التي تتحدث عنها اللقطة؛ لا تستبدل المدينة بكيان مجاور جذاب
  بصرياً.
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


def frame_visual_context(
    story: str,
    frame: dict,
    aliases_fn: Callable[[str], Iterable[str]],
) -> str:
    """Vision-gate context binding a candidate to both story and frame."""
    names = _subject_names(story, aliases_fn)
    label = " / ".join(names[:4]) or str(story or "").strip()
    heading = str(frame.get("heading", "") or "").strip()
    text = str(frame.get("text", "") or "").strip()
    body = "\n".join(v for v in (heading, text) if v)
    return (
        f"القصة كلها عن: {label}.\n"
        "راجع الصورة لهذه اللقطة تحديداً، لا لموضوع القصة عموماً. يجب أن "
        "تُظهر مباشرةً المكان/الشخص/الشيء أو المرحلة التي تصفها اللقطة، "
        "وأن تبقى ضمن بطل القصة المعلن. مجرد ارتباط الصورة بالبطل ليس كافياً. "
        "إذا كانت اللقطة تاريخية فطابق الحقبة أيضاً؛ صورة حديثة لا تمثل "
        "مرحلة قديمة لمجرد أنها للمكان نفسه.\n"
        f"{body}"
    ).strip()


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
    active = {"story": ""}

    def strict_story_photo_shows(photo, context):
        story = active["story"]
        if not story:
            # Outside the frame-selection phase keep the underlying behavior;
            # portrait prechecks and unrelated utilities are not broadened or
            # tightened by this Story-only rule.
            return original_photo_shows(photo, context)

        contract = frame_visual_context(
            story,
            {"heading": "", "text": str(context or "")},
            sb.story_aliases,
        )
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

    def focused_find_all_photos(brief):
        previous = active["story"]
        active["story"] = str((brief or {}).get("story", "") or "").strip()
        try:
            return original_find_all_photos(brief)
        finally:
            active["story"] = previous

    sb.photo_shows = strict_story_photo_shows
    sb.find_all_photos = focused_find_all_photos
    setattr(sb, _CONFIGURED_ATTR, True)
    return sb
