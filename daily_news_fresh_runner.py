"""Daily news entrypoint with strict cross-story visual freshness.

The legacy photo layer keeps a `.recentkeep` escape hatch so older bots can
reuse a recent image when every fresh source is exhausted. That behavior is
wrong for the scheduled News card: a recent image rejected for one ranked
story must never become another story's final fallback.
"""

import os
from pathlib import Path

import daily_news_runner


FINANCIAL_TAKEAWAY_GUIDANCE = """
في الأخبار المالية، اجعل takeaway يشرح ببساطة ماذا يعني الخبر، لا أن يعيد العنوان.
طبّق ذلك خصوصاً على: صكوك، اكتتاب، تمويل، إصدار، نتائج مالية، استحواذ وطرح.
اشرح الأثر المباشر بلغة بسيطة: ماذا حصل للشركة أو المستثمرين أو السوق أو القارئ السعودي.
لا تخمّن أثراً غير موجود في المصدر، ولا تقدّم نصيحة استثمارية.
مثال: «الراجحي جمع تمويلاً من المستثمرين عبر الصكوك لتمويل مشاريع مؤهلة ذات أثر اجتماعي».
""".strip()


def install_financial_takeaway_guidance(news_bot_module):
    """Make finance cards explain significance instead of repeating the event."""
    if FINANCIAL_TAKEAWAY_GUIDANCE not in news_bot_module.SYSTEM_PROMPT:
        news_bot_module.SYSTEM_PROMPT = (
            news_bot_module.SYSTEM_PROMPT.rstrip()
            + "\n\n"
            + FINANCIAL_TAKEAWAY_GUIDANCE
        )
    return news_bot_module


NEWS_VISUAL_QUALITY_GUIDANCE = """
قاعدة جودة إضافية لبطاقات الأخبار: احكم بـ«لا» إذا كانت سيارات أو حافلات
أو حركة مرور لا تخص الخبر تهيمن على مقدمة الصورة، أو إذا حجبت العناصر
الموضوع الأساسي. واحكم بـ«لا» على موقع إنشاء مزدحم أو لقطة رديئة التكوين
تجعل الموضوع غير واضح؛ ازدحام بصري ليس دليلاً على صلة الصورة.
ولا تعتبر منظراً عاماً لمنطقة مالية أو مبنى مكتب دليلاً على صك أو اكتتاب
أو منتج مالي محدد ما لم يظهر اسم الجهة أو المنتج بوضوح. وللمنتجات المالية
الحديثة، ارفض صور العملات القديمة أو أكوام النقود العامة؛ فضّل لقطة تحريرية
حديثة تُظهر المنتج نفسه أو قناة الاكتتاب أو الجهة المشاركة بوضوح.
لكن لا تطبق قاعدة المنتج المالي على خبر تكون فيه السلعة نفسها هي الموضوع:
إذا سمّى العنوان الذهب نفسه وكانت الصورة تُظهر سبائك الذهب بوضوح، فاحكم
بـ«نعم» ما دامت القصة ليست عن منتج مالي مسمّى أو جهة مختلفة. وينطبق ذلك
على السلعة أو الشيء المادي الذي يسمّيه العنوان صراحة، لا على رموز مالية عامة.
""".strip()


NEWS_PHOTO_JUDGE = """قيّم صورة فوتوغرافية لبطاقة خبر واحد، لا لفريم قصة تاريخية.
نص الخبر: {context}
أجب أولاً بكلمة نعم أو محايدة أو لا ثم سبب مختصر.
نعم: صورة حقيقية واضحة للموضوع أو لسياق مباشر محدد؛ صورة الشخص العام
المذكور، منتج الشركة المذكورة، أو نشاط الخبر. لا يلزم أن توثق الصورة
لحظة الحدث أو تثبت الأرقام: صورة وجهة سياحية سعودية معروفة تصلح لخبر
السياحة الداخلية السعودية، وصورة تلفزيون LG تصلح لخبر خصوصية تلفزيونات LG،
وصورة مقر Mistral AI المعروف تصلح لخبر تمويل الشركة. لا تشترط أن يظهر
مبلغ التمويل أو نسبة الزيادة في الصورة. اعتمد على هوية ما يظهر فعلاً.
محايدة: الصلة محتملة لكن هوية الشخص أو المنتج أو المكان غير قابلة للتحقق.
لا: جهة أو شخص آخر، موقع لا يطابق الخبر، صورة تاريخية توحي بحدث حالي،
مشهد عام بلا صلة مباشرة، صورة رديئة، شعار أو رسم أو لقطة شاشة.
لا تعرض هاتفاً تخيلياً أو هاتف شركة أخرى على أنه جهاز Apple القادم.
صورة المصدر ليست دليلاً كافياً وحدها على الصلة. لا تنسب اتهاماً إلى علامة
غير مذكورة. ابق متشدداً في الهوية والجودة دون طلب تصوير أرقام مجردة.
""".strip()


def install_news_visual_quality_guidance(news_bot_module):
    """Reject low-quality or generic imagery in scheduled News only."""
    news_bot_module._VISION_JUDGE = NEWS_PHOTO_JUDGE
    guidance = NEWS_VISUAL_QUALITY_GUIDANCE
    prompt = getattr(news_bot_module, "_VISION_JUDGE", "")
    if guidance not in prompt:
        news_bot_module._VISION_JUDGE = prompt.rstrip() + "\n\n" + guidance
    return news_bot_module


def install_recent_photo_fail_closed(news_bot_module):
    """Prevent scheduled News from recycling a recently used photo."""
    original_local = news_bot_module.fetch_local_photo

    def fresh_local(*args, **kwargs):
        result = original_local(*args, **kwargs)
        out_path = kwargs.get("out_path")
        if out_path is None and len(args) >= 3:
            out_path = args[2]
        photo = result[0] if isinstance(result, tuple) and result else result
        if not photo and out_path:
            Path(str(out_path) + ".recentkeep").unlink(missing_ok=True)
        return result

    def no_recent_fallback(out_path):
        Path(str(out_path) + ".recentkeep").unlink(missing_ok=True)
        print("  ! fresh visual exhausted — refusing recent-photo fallback")
        return None

    news_bot_module.fetch_local_photo = fresh_local
    news_bot_module.recent_fallback = no_recent_fallback
    return news_bot_module


def install_news_notification_labels(news_bot_module):
    """Keep News alerts distinct from the separate Story bot."""
    original_notify = news_bot_module.notify

    def news_notify(text, *args, **kwargs):
        text = str(text).replace(
            "stories had a usable photo", "news items had a usable photo"
        ).replace(
            "model returned no stories", "model returned no news items"
        )
        return original_notify(text, *args, **kwargs)

    news_bot_module.notify = news_notify
    return news_bot_module


def load_news_bot():
    """Load the shared renderer with the approved News theme as its default."""
    # Recovery or local invocations may omit THEME. Scope the default to the
    # executable entrypoint so importing News policy helpers has no side effect.
    os.environ.setdefault("THEME", "light")
    import news_bot
    return news_bot


def main():
    news_bot = load_news_bot()

    daily_news_runner.configure(news_bot)
    install_financial_takeaway_guidance(news_bot)
    install_news_visual_quality_guidance(news_bot)
    install_recent_photo_fail_closed(news_bot)
    install_news_notification_labels(news_bot)
    news_bot.main()


if __name__ == "__main__":
    main()
