#!/usr/bin/env python3
"""
بوت القصص — قصة واحدة في أربع لقطات، تُنشر كسلسلة على سناب شات.

يختار قصة من stories.txt، يبحث عنها، ثم يبني ٤ لقطات:
  ١) المشهد الأول — من أين بدأت
  ٢) المنعطف — اللحظة التي غيّرت كل شيء
  ٣) الرقم — حجم ما صارت إليه
  ٤) الخلاصة — ماذا يعني هذا اليوم

    python story_bot.py
    python story_bot.py "قصة NVIDIA"
"""

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

try:
    from news_bot import (
        ANTHROPIC_API_KEY, DRY_RUN, OUT_DIR, CARDS_DIR, W, H,
        BG_TOP, TEXT, BODY, ACCENT, MUTED, BRAND_INK, RULE,
        ar, load_font, _wrap, _rounded, _clean_model_id,
        commit_and_push, publish_many_via_github, post_story, post_ok,
        describe_failure, notify, notify_album, deliver_unposted, ksa_stamp,
        quota_ok, quota_bump,
        POST_ENABLED, POST_PROVIDER, MEDIA_MODE, upload_media,
        fetch_local_photo, fetch_spa_photo, fetch_openverse_photo,
        fetch_commons_photo, fetch_commons_portrait, fetch_loc_photo,
        fetch_generated_photo, IMAGE_SOURCE, GENERATED_CREDIT,
        photo_shows, vision_gate_summary, draw_brand_badge, seal_photo,
        closing_seal, _photo_digest, register_photos, recent_fallback,
        recent_warning, same_picture, brand_badge,
    )
except ImportError as exc:
    raise SystemExit(
        f"news_bot.py is missing something story_bot needs ({exc}).\n"
        "Upload the latest news_bot.py alongside this file."
    )

STORIES_FILE = Path(os.getenv("STORIES_FILE", "stories.txt"))
USED_FILE = Path("state/stories_used.json")
STORY = os.getenv("STORY", "").strip()
STORY_MODEL = _clean_model_id(os.getenv("STORY_MODEL"), "claude-opus-5")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "").strip() or "16000")
MAX_SEARCHES = int(os.getenv("MAX_SEARCHES", "").strip() or "6")
BRAND = os.getenv("BRAND", "ملخص تنفيذي - قصة")
# 4 is terse, 6 gives a story room to breathe. Snapchat's own guidance
# favours 5-8 frame stories with a clear beginning, middle and end.
STORY_FRAMES = max(4, min(7, int(os.getenv("STORY_FRAMES", "").strip() or "6")))
# generated filler hurts a story more than it helps — off by default here
# OFF by owner decision (2026-08): generated frames disappointed on every
# deck that used them — a fake weathered Mercedes in a generic desert
# closed the SAVOLA story. The ladder falls to the subject's logo instead.
# The generation code (gate, prompt, label) stays dormant behind this flag
# for a future licensed generator; the default and the shipped yaml are OFF.
ALLOW_STORY_GENERATION = os.getenv("ALLOW_STORY_GENERATION", "0").strip() \
    not in ("", "0", "false", "False")
# rather than lose a researched story, let a frame borrow another frame's photo
STORY_ALLOW_REPEAT = os.getenv("STORY_ALLOW_REPEAT", "1").strip() \
    not in ("0", "false", "False")
COOLDOWN_DAYS = int(os.getenv("STORY_COOLDOWN_DAYS", "").strip() or "60")
# a SUBJECT stays retired longer than its line: two entries about one
# entity must not produce two decks months apart feeling like reruns
SUBJECT_COOLDOWN_DAYS = int(
    os.getenv("SUBJECT_COOLDOWN_DAYS", "").strip() or "90")

# The frame-continuation style (connector openings, hanging thoughts, a bare
# pivot line before the turn, a near-empty verdict frame) is modelled on a
# storyteller reference the owner reviewed: each frame resolves the previous
# frame's hanging thought rather than standing alone.
# TODO: replace with real failed-card examples once runs surface them —
# the ✗/✓ pairs in the three new blocks below are placeholders in the house
# style, not yet drawn from cards that actually went wrong.
SYSTEM_PROMPT = """أنت تكتب قصة تُنشر على سناب شات لجمهور سعودي، في {n} لقطات.

القصة ليست خبراً ولا مقالاً. لها بداية ومنعطف ورقم ونهاية تترك أثراً.
ابحث في الإنترنت أولاً، ثم اكتب. كل ما تكتبه يجب أن يكون صحيحاً وموثقاً.

القصة تُروى في {n} لقطات. لها بطل وتوتر، وليست قائمة معلومات.

البناء:
1. العالم والمشكلة — كيف كانت الحياة وقتها، وما الذي كان مستحيلاً حينها.
   لا سيرة ذاتية هنا، ولا تعريف بأحد. اسم واحد على الأكثر في اللقطة كلها،
   وليكن المكان أو الزمن لا الشخص.
   القارئ يجب أن يرى الوضع ويشعر بالمشكلة قبل أن يقابل أي إنسان. اجعله
   يسأل: كيف كان الناس يعيشون هكذا؟ ومن الذي غيّر هذا؟
   ✗ "عبداللطيف جميل كان يبيع البنزين في محطة على طريق مكة القديم."
     (بدأت بالشخص، والقارئ لا يعرف بعد لماذا يهمه هذا الشخص)
   ✓ "في أربعينات القرن الماضي، الطريق بين جدة ومكة كان تراباً. السيارة
      كانت ترفاً لا يملكه إلا القليل. وقطعة الغيار تُطلب من الخارج وتصل
      بعد أشهر — إن وصلت."

2. البطل — الآن قدّم الشخص، وقد صار واضحاً لماذا يستحق أن يُقدَّم.
   من هو، وأين كان يقف من تلك المشكلة تحديداً، وما الذي رآه ولم يره غيره.
   القارئ قابل المشكلة في اللقطة الأولى، فيصل إلى الاسم الآن ومعه سبب
   يجعله يتذكّره. الاسم بلا مشكلة سبقته مجرد معلومة.
   ✓ "في محطة على ذلك الطريق، كان شاب اسمه عبداللطيف جميل يبيع البنزين.
      ورأى ما لم يره غيره: المشكلة ليست في الطريق وحده، بل في أن أحداً
      لا يجلب السيارات التي تتحمّله."

3. المنعطف — القرار أو اللحظة التي كان يمكن أن تمر عادية ثم غيّرت المسار.
   - المنعطف يُفتتح بسطر تحويل قصير مستقل قبل الجسد،
     من ست كلمات أو أقل، يعلن أن القصة ستتغير:
     «وهنا تغيّر كل شيء»، «خلونا نشوف وش صار».
     السطر ليس punch ولا يحمل معلومة — وظيفته
     التهيئة فقط. اكتبه أول جملة في text ثم أكمل الجسد بعده.

4. الثمن — ما الذي كلّفه ذلك؟ رفض، إفلاس وشيك، سخرية، سنوات ضائعة.
   القصة بلا ثمن لا تُصدّق.

5. النتيجة — رقم واحد كبير بمصدره وتاريخه، مربوط بالبداية:
   "من أربع سيارات إلى ربع مليون".

6. الحكم — القصة تنتهي بحكم واضح، لا بسؤال مفتوح.
   بعد قراءة هذه اللقطة يجب أن يعرف القارئ: نجحت أم فشلت؟ وأن يستطيع قولها
   في جملة واحدة لصديقه. ليست تلخيصاً ولا وعظاً، لكنها ليست ملاحظة محايدة
   أيضاً — قل ما انتهت إليه القصة، مسنوداً بما رويته.

   ابنِ الحكم على ما تغيّر ولا يعود، لا على رقم قد ينقلب السنة القادمة.
   الرقم يثبت الحجم، والحكم يقوم على الأثر:
   ✗ "الشركة التي اقتربت من الموت مرتين لا تملك سنة واحدة مضمونة"
     (تنتهي بسؤال مفتوح: القارئ لا يعرف أقصة نجاح قرأ أم قصة تعثّر)
   ✓ "قد تتراجع سنة أو سنتين — لكنها غيّرت ما يصنعه الجميع"

   لقطة الحكم تحمل الحكم ودليله فقط. وإن كان في القصة تراجع أو ثمن ما زال
   قائماً فمكانه لقطة سابقة — لقطة الثمن — لا هنا. القارئ وصل إلى آخر
   البطاقة ليعرف ما انتهت إليه القصة، لا ليوازن بين كفّتين.
   ✗ "نجحت، لكن مبيعاتها تراجعت سنتين" (يفتح ملفاً جديداً في سطر الختام)
   ✓ "نجحت، والدليل أن الصناعة كلها تبعتها"

   واحذف من هذه اللقطة كل تفصيل لا يخدم الحكم، مهما كان صحيحاً: حصة سوقية
   صغيرة، فرع افتُتح، رقم ثانوي. هذه حواشٍ، والختام ليس مكان الحواشي —
   التفصيل الباهت في آخر سطر يُنسي القارئ القصة كلها.

   والحكم يكون على بطل القصة، لا على غيره. البطل الذي حملها ست لقطات هو
   من يُقال في آخرها ما انتهى إليه. ولا تسلّم الختام لمن ظهر في اللقطة
   الأولى لتصف به العالم، ولو كان ما فعله لاحقاً أوضح دليل على التغيير —
   فذلك يمنح آخر كلمة لمن لم يحمل القصة.
   ✗ قصة عن Tesla تنتهي بعدد الطرازات الكهربائية عند General Motors
   ✓ قصة عن Tesla تنتهي بما أثبتته Tesla وتبعها فيه الجميع

   ولا تُعِد في الختام صياغة العنوان. القارئ قرأه في اللقطة الأولى، فإن
   وجده مرة أخرى في آخر سطر خرج بلا شيء جديد، وبدت اللقطات الخمس بينهما
   بلا فائدة. العنوان يَعِد، والختام يثبت.
   ✗ العنوان "السيارة التي أُتلفت ثم عادوا يبيعونها"، ثم الختام "الشركة
     التي أتلفت سياراتها عادت تبيعها"
   ✓ ختام يقول ما لم يكن القارئ يعرفه قبل أن يقرأ القصة

   والحكم يُكتب بصيغة الحاضر. لقطة ختام تؤرّخ نفسها بسنة ماضية («منذ
   2006 وهي الأولى...») صارت لقطة تاريخية سادسة لا حكماً — الحكم يقف
   في اليوم وينظر إلى ما لن يعود كما كان. ولا يعني الحاضرُ رقماً
   حديثاً: حصة سوقية أو إيراد آخر سنة إحصاءة لا حكم.
   ✗ «منذ 2006 تتصدر مبيعات التلفاز عالمياً» (مؤرّخة في الماضي)
   ✗ «حصتها اليوم 31% من سوق الهواتف» (إحصاءة حاضرة، لا حكم)
   ✓ «المحل الذي باع السمك المجفف صار يصنع ذاكرة العالم» (حاضر، بلا
     رقم، ولا يعود كما كان)

   ولا تعطِ رقماً واحداً معنيين متضادين. إن كان الرقم في لقطة النتيجة دليل
   نجاح فلا يصير في لقطة الحكم دليل تراجع — القارئ يقرأ اللقطتين متتاليتين،
   فيظن أنك ناقضت نفسك ويخرج بلا خلاصة.
   ✗ اللقطة 5 "من 500 إلى 1.65 مليون" ثم اللقطة 6 "تراجعت إلى 1.64 مليون"

   - إطار الحكم هو الأخف نصًّا في القصة: جملة واحدة
     في الجسد كحد أقصى، والـpunch يحمل الحكم نفسه.
     إذا احتاج الحكم شرحًا فهو ليس حكمًا بعد.
     وهذا القيد يعلو على ما سبق: كل قواعد الحكم أعلاه باقية، لكن إن
     اقتضى أيٌّ منها جسداً أطول، فالجملة الواحدة هي الحد.
   ✗ جسد من ثلاث جمل يلخص الرحلة ثم punch يكررها.
   ✓ جسد: «اليوم تُدرَّس القصة في كليات الإدارة.»
     punch: «الفكرة التي رفضها الجميع صارت هي القاعدة.»

من اللقطة الثالثة فصاعداً تنطبق قاعدة التسليم أدناه: كل لقطة تُسلّم التي بعدها.

إن طلبت لقطات أقل من ٦: ادمج الثمن مع المنعطف، ثم النتيجة مع الحكم.
واللقطتان الأولى والثانية لا تُدمجان أبداً — الفصل بينهما هو أصل هذا البناء.
إن طلبت ٧، افصل المنعطف عن نتيجته المباشرة.

قواعد تسري على كل لقطة:

- اسمان جديدان على الأكثر في اللقطة الواحدة (شخص، شركة، مكان، منتج، جهاز)،
  وكل اسم يسبقه وصف يقول ما هو:
  ✓ "شركة Fairchild لصناعة الرقائق"   ✗ "Fairchild"
  ✓ "مدينة شنتشن الصناعية جنوب الصين"  ✗ "شنتشن"
  اللقطة التي تذكر أربعة أسماء لم يسمع بها القارئ ليست قصة، بل ملخّص —
  والقارئ يتوقف عندها لأنه فقد الخيط، لا لأنه اهتم.
  إن احتجت اسماً ثالثاً فاللقطة تحمل أكثر مما تحتمل: انقل الزائد إلى لقطة
  أخرى، أو احذفه. القصة لا تحتاج كل ما وجدتَه في البحث.

- معلومة واحدة في الجملة الواحدة. الجملة التي تحمل ثلاث معلومات تُقرأ مرة
  ولا تُفهم، والقارئ على سناب شات لا يعيد القراءة.
  ✗ "أسس شركته سنة 1945 في جدة برأس مال 500 ريال بعد أن ترك عمله في
     المحطة، ثم وقّع مع Toyota سنة 1955."
  ✓ "سنة 1945 أسس شركته في جدة. رأس المال كان 500 ريال. وبعد عشر سنوات
     وقّع مع شركة Toyota اليابانية."

قواعد الربط بين الإطارات:
- كل إطار من الثاني إلى السادس يبدأ بأداة ربط تُكمل
  فكرة الإطار السابق نحويًا: لكن، لأن، وإذا، ولذلك،
  وحتى، وهكذا. الإطار الأول فقط يبدأ بلا رابط.
- آخر جملة في كل إطار تفتح سؤالًا يجيب عنه رابط
  الإطار التالي. الجملة نفسها مكتملة — المعنى هو
  الذي يبقى معلّقًا.
✗ إطار ينتهي: «وأصبح المصنع الأكبر في المنطقة.»
  ثم إطار يبدأ: «في عام 1974 حدث حريق.»
✓ إطار ينتهي: «وأصبح المصنع الأكبر في المنطقة —
  لكن أحدًا لم يسأل من أين يأتي الوقود.»
  ثم إطار يبدأ: «ولذلك حين ارتفع سعر النفط...»

قاعدة التسليم بين اللقطات — الأهم في القصة:

- كل اسم (شخص، شركة، مكان، منتج) يجب أن يُقدَّم عند أول ذكر له: من هو،
  وما علاقته بالبطل. لا يظهر اسم فجأة كأن القارئ يعرفه.
  ✗ اللقطة 3: "Fairchild أرسلت لوسون ليفحص النموذج" — ومن أين جاءت Fairchild؟
  ✓ اللقطة 2 تنتهي بـ: "وفي 1970 دخل Jerry Lawson شركة Fairchild لصناعة
     الرقائق، مهندساً في قسم المبيعات."
     ثم اللقطة 3 تبدأ بـ: "وهناك وصله نموذج غريب..."

- كل لقطة تبدأ بما يربطها بالتي قبلها: ضمير، أو إشارة، أو أداة سرد.
  "وهناك"، "وبعد سنتين"، "لكن المشكلة أن"، "هذا الجهاز".

- اللقطة التي تبدأ باسم جديد بلا تمهيد تكسر القصة. اقرأ كل لقطة وحدها
  واسأل: هل فيها اسم لم يُشرح من قبل؟ إن كان الجواب نعم، أضف التمهيد
  في اللقطة السابقة لا في هذه.

- نهاية كل لقطة تفتح سؤالاً تجيب عنه التي بعدها. القارئ ينتقل لأنه يريد
  أن يعرف، لا لأن هناك لقطة أخرى.

الربط بين اللقطات:
- كل لقطة تكمل التي قبلها. استخدم أدوات السرد: "لكن"، "وفي تلك السنة"،
  "ما توقّع أحد"، "وهنا".
- اللقطة التي تصلح للوقوف وحدها بلا ترتيب ليست جزءاً من قصة، بل معلومة.
- اختبار قبل التسليم: اقرأ اللقطات بالترتيب. هل تُقرأ كحكاية متصلة؟
  إن لم تكن كذلك، أعد الكتابة.

- الاختبار الأخير، ولا تسلّم قبل أن تجريه: اقرأ القصة بعين قارئ لا يعرف
  شيئاً عن الموضوع — لا عن الشخص، ولا عن البلد، ولا عن الصناعة، ولا عن
  تلك الحقبة. هل يستطيع متابعة كل لقطة بما قرأه في اللقطات السابقة وحدها؟
  إن احتاجت لقطة معرفة لم تعطها القصة من قبل، فالخلل في اللقطة التي قبلها
  لا في هذه: أضف التمهيد هناك. وإن لم يبقَ في تلك اللقطة مكان، فاحذف
  التفصيل الذي يحتاج التمهيد — القصة التي تُفهم أهم من القصة الكاملة.

قواعد الكتابة:
- عربية بسيطة قريبة من كلام الناس، لا لغة كتب.
- كل لقطة فكرة واحدة فقط. جمل قصيرة.
- كل رقم بوحدته وتاريخه ومصدره. لا تخمّن ولا تقرّب بلا داعٍ.
- أسماء الشركات والأشخاص الأجانب بالإنجليزية: Apple، Steve Jobs، NVIDIA.
- أما الأسماء السعودية والعربية فبالعربية دائماً، حتى لو شاع تداولها بحروف
  لاتينية أو كان اسمها الرسمي بالإنجليزية:
  ✓ مرايا، أرامكو، نيوم، الدرعية، العلا، طيران ناس
  ✗ Maraya، Aramco، NEOM، Diriyah، AlUla، flynas
- الأرقام لاتينية: 1976 لا ١٩٧٦.
- تجنّب اللغة الرسمية والوعظ. لا "وهكذا نتعلم أن".
- استخدم الفعل المحايد لا العنيف حين تصف ما جرى لشيء أو لمشروع أو لشركة.
  الفعل العنيف يضيف انفعالاً لا تحتاجه القصة، ويوحي بقسوة لم تقع فعلاً.
  ✗ سحقت السيارات    ✓ أتلفت السيارات
  ✗ دمّرت المشروع     ✓ أوقفت المشروع
  ✗ أبادت الأسطول     ✓ سحبت الأسطول من الخدمة
  وكذلك في وصف البطل: خسر، تعثّر، أُقصي، أُبعد — لا "سُحق" ولا "دُمّر".
  الواقعة تكفي بذاتها، والوصف الهادئ يجعلها أثقل لا أخف.
- إن لم تجد مصادر موثوقة للقصة، أعد title = "لا توجد مصادر كافية" واشرح.
- عنوان القصة في stories.txt هو اقتراح لا حقيقة. كثير من قصص المشاهير
  متداولة بصيغة مبالغ فيها أو غير مؤكدة (منديل، ورقة جامعية، رفض عرض).
  تحقق من الرواية أولاً: إن كانت مؤكدة فاروِها، وإن كانت مختلَفاً عليها فقل ذلك
  صراحة في اللقطة نفسها ("الرواية المتداولة... لكن المصادر الموثوقة تقول").
  وإن ثبت أنها غير صحيحة، اروِ القصة الحقيقية بدل الشائعة.
- للأشخاص الأحياء: التزم بالوقائع الموثقة فقط. لا تنسب لهم أقوالاً ولا نوايا،
  ولا تتحدث عن ثرواتهم أو حياتهم الخاصة إلا بما نشرته مصادر رسمية.

قواعد المقارنة بين رقمين:
- لا تقارن رقمين إلا إذا كانا قابلين للمقارنة فعلاً: نفس الوحدة، نفس الفترة،
  ونفس الأساس.
- مكوّنات المؤشر الواحد ليست متنافسة. الإيجار والغذاء كلاهما جزء من مؤشر
  أسعار المستهلك بأوزان مختلفة، فمقارنة ارتفاعهما ببعض تُضلّل القارئ.
  ✗ "الإيجارات ارتفعت 4.3% بينما الغذاء 1.5% فقط"
  ✓ "السكن أكبر بند في سلة المؤشر، فارتفاعه 4.3% هو ما رفع الرقم العام"
- إن كان أحد البندين يحرّك الرقم العام أكثر، فقل ذلك بوزنه في السلة، لا
  بمقارنته ببند آخر.
- المقارنة الصحيحة تكون بين الشيء ونفسه عبر الزمن، أو بينه وبين نظيره في
  سوق آخر.
- القصة تتبع كياناً واحداً مسمّى وتثبت عليه. المجموعة الأم وشركتها التابعة
  كيانان مختلفان: لا تضع رقم تأسيس الأم بجوار رقم إيرادات التابعة كأنهما
  خط واحد إلا إذا سمّيت الانتقال بين الكيانين صراحة في النص نفسه.
  ✗ «بدأت بثلاثين ألف وون (1938) واليوم إيراداتها 333.6 تريليون وون» —
    الأول لشركة التجارة الأم والثاني لشركة الإلكترونيات التابعة،
    والقارئ يظنهما شركة واحدة.
  ✓ «من شركة التجارة الأم وُلدت شركة الإلكترونيات عام 1969 — وهي وحدها
    التي بلغت إيراداتها 333.6 تريليون وون في 2024»

الأنظمة والقواعد السعودية:
- إذا كان الموضوع يمسّ مجالاً تنظّمه الدولة — الإيجارات، الرواتب، مكافأة
  نهاية الخدمة، الرسوم، التأمين، حماية المستهلك، الدفع الآجل، عقود العمل —
  فابحث عن النظام الساري قبل الكتابة، واذكره في البطاقة.
- البطاقة التي تعطي نصيحة عملية وتغفل النظام الذي يحكمها بطاقة ناقصة، حتى لو
  كانت كل أرقامها صحيحة.
- اذكر النظام بصيغته الحالية ومصدره الرسمي، وتاريخ آخر تحديث إن وُجد.
- مثال: بطاقة عن ارتفاع الإيجارات تنصح بتجديد العقد، دون ذكر ما إذا كان هناك
  سقف نظامي لرفع الإيجار، بطاقة مضلّلة.
- إن لم تجد نظاماً واضحاً، قل ذلك صراحة بدل الصمت عنه.

المالية العامة والسياسات الحكومية:
- انقل الرقم ومصدره، ولا تُصدر حكماً على أداء الدولة أو وتيرة
  سياساتها. «ببطء»، «متعثر»، «متأخر»، «نجح»، «فشل» أحكام —
  لا تُكتب إلا منسوبة إلى جهة قالتها، بمصدرها.
- لا حكم على الوتيرة (سريع/بطيء) بلا مقياس معلن في البطاقة
  نفسها: مستهدف رسمي منشور، أو نظير محدد قابل للمقارنة.
  إن وُجد المقياس فاذكره وانسبه؛ وإن لم يوجد فلا حكم.
- لا تخاطب القارئ بوصفه المموِّل («كل ريال تدفعه») ولا تصغ
  إيرادات الدولة كأنها مأخوذة منه. صفها بصيغتها الرسمية.
- ربع واحد لا يصنع اتجاهاً: مقارنة سنوية لربع واحد لا تتحول
  إلى معدل نمو «سنوي» مستمر.
✗ «كل ريال تدفعه ضريبة أو رسم حكومي يظهر في هذا الرقم»
✓ «الإيرادات غير النفطية — ضرائب ورسوم وعوائد استثمار —
   بلغت 153.7 مليار ريال في الربع الثاني»
✗ «التنويع يتقدم ببطء: نمو 3% سنوياً في الدخل غير النفطي»
✓ «45% من إيرادات الربع جاءت من غير النفط — النسبة التي
   تُقاس بها خطة التنويع» (وإن وُجد مستهدف رسمي معلن،
   فاذكره بمصدره وقارن به)

لكل لقطة:
- heading: سطر قصير جداً (حتى ٣٠ حرفاً) — يظهر كبيراً
  والعنوان يصف لقطته هي: حدثَها وزمنَها. لا تسحب خطّاف لقطة لاحقة إلى
  لقطة مبكرة مهما كان أقوى — الخطّاف القوي يبقى في لقطته هو.
  والأرقام والسنوات تبقى في text لا في العنوان: العنوان يصفها بالكلمات
  ولا يسحبها إليه — لقطة نصّها بلا رقم ولا سنة تفقد معالجتها البصرية.
  ✗ لقطة 1938 عن تاجر سمك مجفف عنوانها «150 ألف جهاز احترقت في يوم
    واحد» — هذا حدث 1995 ومكانه اللقطة الرابعة حيث يقع.
- text: من جملتين إلى أربع جمل (١٢٠ إلى ٢٨٠ حرفاً).
  خذ راحتك: القصة المضغوطة تفقد معناها. اشرح السبب والنتيجة،
  لا العناوين فقط. لكن بلا حشو — كل جملة تضيف شيئاً جديداً.
  واللحظة الواحدة تُروى مرة واحدة في القصة كلها. إن ختمت لقطةٌ بلحظةٍ
  (وفاة المؤسس، توقيع الصفقة) فاللقطة التالية تبدأ مما بعدها ولا
  تعيد روايتها بصياغة أخرى.
  ✗ اللقطة الرابعة تختم «توفي سنة 1987 قبل أن تصل شركته إلى المركز
    الأول» ثم الخامسة تفتتح بإعادة وفاته — اللحظة نفسها مرتين.
  ✓ الخامسة تبدأ بما فعله الابن الوارث سنة 1988 — الموت وقع في
    الرابعة، والخامسة تكمل.
- punch: اتركها فارغة "" في أغلب اللقطات.
  لا تملأها إلا إذا كان في اللقطة لحظة واحدة تستحق أن تقف وحدها: اقتباس قيل
  فعلاً، أو حكم، أو انقلاب في المسار. تُعرض بالأحمر وحدها تحت النص، ولذلك
  تُقرأ كأنها ذروة اللقطة — فإن وضعت فيها كلاماً عادياً بدت البطاقة كأنها
  تصيح بلا سبب.
  جملة واحدة قصيرة (حتى ٧٠ حرفاً). ولا تكرر ما في text بصياغة أخرى:
  هي جملة جديدة، لا خلاصة.
  وإن كانت اللقطة عن مالية الدولة أو سياساتها، فالسطر الأحمر يحمل دلالة
  الرقم لا حكماً على أداء الدولة — انظر قواعد المالية العامة أعلاه.
  ✗ "وهكذا نجح المشروع" (تلخيص، وليس لحظة)
  ✗ "كانت تلك بداية التغيير" (كلام عام لا يقول شيئاً)
  ✗ إعادة صياغة آخر جملة في text
  ✓ "قالوا له: لا أحد يشتري سيارة في بلد بلا طرق معبّدة."
  ✓ "خسر كل شيء في ثمانية عشر شهراً."
  ✓ "الرقم لم يتغير منذ ذلك اليوم: 3.75"
  في القصة كلها: لقطة واحدة أو لقطتان على الأكثر تحمل punch، والبقية "".
  إن وضعتها في كل لقطة فقدت أثرها وصارت زخرفة — القوة في ندرتها.
  واللقطة الأخيرة أنسب مكان لها: ضع الحكم فيها، فيقرأه القارئ وحده
  بالأحمر. حين تحمل اللقطة الأخيرة punch يعود نصها إلى اللون العادي،
  فيبقى الأحمر على سطر واحد لا على البطاقة كلها.

- subject_kind: نوع موضوع هذه اللقطة تحديداً — كلمة واحدة من:
  "company" (شركة أو منتج) | "place_country" (دولة) |
  "place_city" (مدينة أو منطقة) | "person" (شخص) |
  "abstract" (مفهوم أو سياسة أو حقبة أو مشهد عام).
  القصة الواحدة تخلط الأنواع: لقطة البطل person ولقطة الختام company.
  قاعدة الأمان: إن لم تكن متأكداً فاكتب "abstract" — الشك لا يتحول
  أبداً إلى علم دولة خاطئ أو شعار شركة خاطئ.
  ✓ لقطة عن Steve Jobs نفسه: "person"
  ✓ لقطة ختام عن Apple: "company"
  ✓ لقطة عن الصين وسياساتها: "place_country"
  ✓ لقطة عن حي شكو في شينزن: "place_city"
  ✓ «قرية صيد صغيرة» أو «الإصلاح الاقتصادي»: "abstract"
  ✗ لقطة عن «الانفتاح الصيني» موسومة "place_country" — المفهوم abstract
    وإن ورد اسم البلد في النص
  والجهات والمؤسسات الرسمية (وزارة، هيئة، جامعة) عاملها "company" —
  شعارها الرسمي أو صورة مبناها يقومان مقام العلامة التجارية. أما
  التقنيات والأحداث التاريخية فـ"abstract" وصورها أرشيفية من حقبتها.

- image_keywords: من كلمتين إلى أربع كلمات إنجليزية بسيطة للبحث عن صورة
  حقيقية. أسماء علم فقط: اسم الشخص أو الشركة أو المنتج أو المكان.
  ✓ ["Steve Jobs", "Macintosh 128K", "Apple Park"]
  ✗ ["a garage in California in 1976"]   ✗ ["office building", "modern desk"]

  الكلمة تسمّي شيئاً يتحدث عنه نص هذه اللقطة نفسها — موضوع القصة، لا
  كيانات مجاورة له في البحث: الراعي والشريك والمستثمر والعميل والملعب
  ليسوا موضوع القصة، ولا يدخلون الكلمات إلا إذا كان نص اللقطة عنهم هم.
  قصة عن الشركة X لا تأخذ ملعب النادي الذي رعته X صورةً لأي لقطة.
  ✗ قصة عن تطبيق مرسول، وإطار صورته «نادي النصر» لأن مرسول رعى النادي
  ✓ إطار صورته «مرسول» أو شعارها، أو المدينة/المشهد الذي يصفه النص

  وفي لقطة عن شخص، image_keywords أسماء أشخاص فقط — لا فنادق ولا قاعات
  ولا أماكن الإعلان: مسار الصور في لقطات الأشخاص يبحث عن بورتريه لكل
  كلمة، واسم المكان يعود مبنىً بصورته الحديثة.
  ✗ ["Lee Byung-chul", "Hotel Okura Tokyo"] على لقطة إعلان 1983 —
    عادت الكلمة الثانية برجاً زجاجياً بُني سنة 2019.

  مهم: اختر أسماء يُرجّح وجود صور لها في أرشيف مفتوح المصدر. الأشخاص
  والشركات والمنتجات المشهورة لها صور؛ الأشخاص المغمورون وأحداث بعينها
  غالباً لا. إن كان البطل نادر الصور، أضف اسم منتجه أو شركته أو مدينته
  ككلمة ثانية في نفس اللقطة — بطاقة بلا صورة تُلغي القصة كلها.

  اللقطة الأولى: المكان أو الزمن الذي وصفته — لا وجه أحد، فالبطل لم يظهر
  بعد. صورة للمكان كما كان، تُري القارئ العالم الذي تتحدث عنه اللقطة.
  ✓ ["Jeddah 1940s", "Mecca old road", "Riyadh 1960s", "Shekou industrial zone"]

  اللقطة الثانية: صورة البطل نفسه. ضع اسمه الكامل أولاً في القائمة.
  القارئ قابله للتو في النص، وهذه أول مرة يرى فيها وجهه.
  ✓ ["Abdul Latif Jameel", "Sulaiman Al Rajhi", "Ali Al-Naimi"]

  بقية اللقطات: المنتج أو الشركة أو المكان المذكور في تلك اللقطة تحديداً.
  لا تضع كلمات عامة (مكتب، مبنى، موظفون) — الصورة العامة أسوأ من لا شيء
  لأنها تبدو حشواً. اختر ما تتوقع وجوده فعلاً في أرشيف صور.

  الكلمة تسمّي شيئاً مذكوراً في هذه اللقطة، لا مزاجاً ولا جواً عاماً.
  ولا تطلب لقطة قريبة أو مادة أو ملمساً (texture) لمجرد أنها تبدو جميلة:
  الصورة الواسعة المرتبطة باللقطة أفضل من لقطة قريبة لا علاقة لها بها.
  القارئ يقرأ الصورة مع النص، فإن لم تكن منه بدت زينة مقحمة.
  ✗ ["dust texture", "close-up circuit board", "vintage paper", "old machinery"]
  ✓ ["Fairchild Semiconductor", "Channel F console", "San Jose factory"]
  اسأل نفسك: هل هذه الكلمة اسم شيء ورد في نص هذه اللقطة؟ إن كان لا، غيّرها.

  وللقطة التاريخية قاعدة أدق: سمِّ حدث اللقطة بمكانه وزمانه، لا الكيان
  المعاصر الذي يذكره النص عرضاً. أرشيف الصور يفهرس الاسم المعاصر بصوره
  الحديثة، فترجع طائرة الشركة اليوم للقطة تدور سنة 1938، وجسر سان
  فرانسيسكو للقطة عن اجتماع في مكاتبها، وناقلة تحمل اسم المدينة للقطة عن
  بئر فيها — كلها وقعت فعلاً.
  ✗ ["Aramco"] للقطة عن تدفق النفط سنة 1938 — ترجع طائرتها الحديثة
  ✗ ["San Francisco"] للقطة عن اجتماع الإدارة — يرجع الجسر
  ✓ ["Dammam No. 7 1938", "Dhahran drilling 1930s"]
  ✓ ["CASOC geologists 1935"]
  الصيغة: الشيء + المكان أو السنة. إن لم تكن للحدث صورة بهذه الصيغة،
  فالأقرب زمناً ومكاناً — لا الأشهر اسماً.

  كل كلمة يجب أن تسمّي واحداً من أربعة فقط: مكاناً، أو منتجاً، أو مبنى،
  أو شخصاً. لا فكرة، ولا حقبة، ولا حدثاً تاريخياً، ولا شعاراً، ولا سياسة.
  الفكرة لا تُصوَّر، فالأرشيف لا يملك لها صوراً — يملك ما رُسم عنها: ملصقات
  دعائية ولوحات وكاريكاتير. وهذه أعمال فنية تحمل رأياً، لا صوراً لما حدث،
  ووضعها في قصة عن شخص حقيقي يحوّل رأي رسّام إلى وثيقة.
  ✗ "Cultural Revolution" — يرجع ملصقات دعائية ورسومات، لا صوراً
  ✓ "Shekou industrial zone" — يرجع صورة فوتوغرافية للمكان نفسه
  ✗ "economic reform"، "the oil boom"، "independence"، "Vision 2030"
  ✓ "Jubail port"، "Ghawar oil field"، "King Fahd Causeway"
  القاعدة: إن لم تستطع تخيّل مصوّراً واقفاً أمام هذا الشيء يلتقط له صورة،
  فهي ليست كلمة بحث — استبدلها باسم شيء مادي وُجد في تلك اللقطة.

- image_keywords_ar: نفس أسماء هذه اللقطة بالعربية — من كلمة إلى ثلاث،
  أسماء علم فقط، لا وصفاً ولا جملة. لكل لقطة كلماتها هي، لا كلمات القصة كلها.

  أرشيف الصور قد لا يفهرس الاسم إلا بالعربية، فيرجع البحث اللاتيني فارغاً
  عن موضوع له صور فعلاً. هذه القائمة هي ما ينقذ اللقطة في تلك الحالة.

  لكل اسم سعودي أو عربي ضع الاسم العربي هنا دائماً، حتى لو كان للجهة اسم
  لاتيني رسمي وكتبتَه في image_keywords — الاسم العربي هو ما فُهرست به الصورة:
  ✓ image_keywords: ["Aramco"]   مع   image_keywords_ar: ["أرامكو"]
  ✓ image_keywords: ["AlUla"]    مع   image_keywords_ar: ["العلا", "الحِجر"]
  ✓ image_keywords: ["Abdul Latif Jameel"] مع ["عبداللطيف جميل"]
  ✗ لقطة عن موضوع سعودي وقائمتها العربية فارغة

  وإن كانت اللقطة عن موضوع أجنبي بحت لا اسم عربي متداول له
  (Jerry Lawson، Fairchild، Macintosh) فاتركها فارغة: []

واكتب أيضاً:
- title: عنوان القصة كاملاً (حتى ٤٥ حرفاً) — يظهر في اللقطة الأولى
- caption: نص المنشور المرافق (حتى ١٢٠ حرفاً)
- sources: أسماء المصادر فقط، من ٢ إلى ٤. اسم الجهة أو الموقع،
  لا عنوان المقال ولا الرابط.
  ✓ ["الهيئة الملكية للعلا", "UNESCO", "Guinness"]
  ✗ ["The revival of AlUla's Old Town: courier.unesco.org"]
- image_queries: ثلاث عبارات إنجليزية لصورة اللقطة الأولى، مشهد ملموس
  بلا أشخاص ولا شعارات ولا نصوص
- image_queries_ar: أسماء علم عربية للبحث في أرشيف الصور السعودي — من
  كلمة إلى ثلاث، بنفس معيار image_keywords_ar. لا كلمات عامة ولا فئات.
  ✗ «صحراء» على لقطة البطل أعادت صورة سياحية من تونس
  ✓ ["الظهران", "بئر الدمام", "الملك عبدالعزيز"]
- image_prompt: وصف إنجليزي لمشهد واحد متماسك، بلا نصوص ولا وجوه

أجب بصيغة JSON فقط:
{{"title": "...", "caption": "...", \
"frames": [{{"heading": "...", "text": "...", "punch": "", \
"subject_kind": "...", \
"image_keywords": ["...", "...", "..."], "image_keywords_ar": ["..."]}}], \
"sources": ["..."], "image_queries": ["..."], "image_queries_ar": ["..."], \
"image_prompt": "..."}}"""

# --------------------------------------------------------------------------
# Is this story about a person, and can we show their face?
# --------------------------------------------------------------------------
# A person-led story with no portrait is not worth researching: the reader
# meets the protagonist in frame 2 and there is nothing to show them. The
# check costs two image searches; the research call it avoids is an Opus
# request with web search, so failing early is much the cheaper mistake.

SKIPPED_FILE = Path("state/stories_skipped.json")
# short: a portrait may appear later, and more often the name simply did not
# search well — this is not a verdict on the story
STORY_SKIP_DAYS = int(os.getenv("STORY_SKIP_DAYS", "").strip() or "14")
STORY_ATTEMPTS = int(os.getenv("STORY_ATTEMPTS", "").strip() or "5")
# one quiet miss is routine; a run of them means the sources are down or the
# list has drifted, and that is worth a message
PORTRAIT_ALERT_AFTER = int(os.getenv("PORTRAIT_ALERT_AFTER", "").strip() or "3")

# An Arabic head of two or three words looks exactly like a person's name, so
# these are what separate "جواز السفر" and "جدة التاريخية" from "علي النعيمي".
NOT_A_PERSON = {
    # generic subjects
    "صندوق", "جواز", "أزمة", "الطيران", "شركة", "بنك", "مصرف", "مجموعة",
    "مؤسسة", "هيئة", "وزارة", "سوق", "بورصة", "متجر", "مصنع", "جامعة",
    "مطار", "ميناء", "طريق", "جسر", "قطار", "مترو", "برج", "قصة", "تاريخ",
    "الأخوان", "الإخوان", "عائلة", "أسرة", "جيل", "أول", "صناعة", "تجارة",
    # places that appear as heads in their own right
    "الرياض", "جدة", "مكة", "المدينة", "الدمام", "الخبر", "العلا", "نيوم",
    "سنغافورة", "نيويورك", "دبي", "لندن", "طوكيو", "باريس", "الصين",
    "السعودية", "المملكة", "الخليج", "أمريكا", "اليابان",
    # adjectives that follow a subject, never a surname
    "التاريخية", "المدني", "العامة", "الوطني", "الدولي", "العالمي",
    "الحديثة", "القديمة", "الكبرى", "الجديد", "الجديدة",
}
# a head carrying one of these is a phrase, not a name
_PARTICLES = {"في", "من", "إلى", "على", "عن", "مع", "بين", "حول", "بعد", "قبل"}
# a question is never a name — "كيف أفلست دولة؟" parses as three plain Arabic
# words and would otherwise sail through
_QUESTIONS = {"كيف", "لماذا", "ماذا", "متى", "أين", "هل", "كم", "أي", "لِمَ"}

_LATIN_NAME = re.compile(r"^[A-Z][A-Za-z.'\-]+(?: [A-Z][A-Za-z.'\-]+){1,3}$")
_ARABIC_WORD = re.compile(r"^[\u0621-\u064A]{2,}$")


def person_name(story):
    """The person a story is about, or "" when it is about something else.

    Deliberately cautious. A miss just means no pre-check, which is what the
    bot did before; a false positive would skip a good story about a company
    because no portrait of it exists.
    """
    key = str(story or "").strip()
    if not _ALIASES_LOADED:
        load_stories()
    declared = _STORY_PERSONS.get(key)
    if declared is not None:
        # a typed line is authoritative: its first person, or NO person —
        # the heuristic once read «نون» as a name and probed a portrait
        return declared[0] if declared else ""
    head = re.sub(r"^\s*قصة\s+", "", key)
    head = head.split(":")[0].split("؟")[0].strip(" -—،")
    if not head:
        return ""

    if _LATIN_NAME.match(head):          # "Steve Jobs", "Mary Allen Wilkes"
        return head                      # one word is a company: NVIDIA, Tesla

    words = head.split()
    if not 2 <= len(words) <= 4:
        return ""
    if any(w in _PARTICLES or w in _QUESTIONS or w in NOT_A_PERSON
           for w in words):
        return ""
    if all(_ARABIC_WORD.match(w) for w in words):
        return head                      # "علي النعيمي", "محمد بن لادن"
    return ""


# Aliases: the archive searches ITS name for a person, not the story's —
# «علي النعيمي» found nothing while "Ali Al-Naimi" carries a lead portrait,
# and every Commons file of Sarah Breedlove is titled "Madam C. J. Walker".
# A story line may carry the archive's names after a pipe, same extension
# pattern as topics.txt:
#     قصة علي النعيمي | Ali Al-Naimi
# The left side stays the story everywhere (display, choose_story identity,
# used/skipped state keys); aliases feed only the portrait pre-check and the
# research call. Built by load_stories, looked up by exact story text.
_STORY_ALIASES = {}
# Pools: a `# @pool: <name>` marker line assigns every subsequent story to
# that pool until the next marker; lines before any marker are "general"
# (the original list is general by default). Ordinary # lines stay
# comments — the batch's category labels are not stories.
_STORY_POOLS = {}
# explicit `logo:domain.com` tokens from the alias tail — the ONLY identity
# the auto-logo fetch will accept. Title-derived slugs are dead: they are
# how a wrong company's mark gets guessed onto a story.
_STORY_LOGO_DOMAIN = {}
# explicit `subject:key` tokens — the canonical entity key for dedupe,
# for lines whose identity isn't obvious from aliases
_STORY_SUBJECT = {}
# saudi-pool lines with NO identity at all (no Latin alias, no subject:,
# no logo:) — excluded from selection and listed once at load, never
# discovered mid-run: with subject binding on, such a line has nothing
# to search on and cannot be illustrated
_STORY_PERSONS = {}      # head -> declared person aliases ([] = none, typed)
_STORY_CONTEXT = {}      # head -> corroborating context tokens
_UNIDENTIFIED = set()
_UNIDENTIFIED_ANNOUNCED = False
_DUPES_ANNOUNCED = False
_ALIASES_LOADED = False


def load_stories():
    global _ALIASES_LOADED
    try:
        lines = STORIES_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print(f"  ! {STORIES_FILE} not found")
        return []
    stories = []
    _STORY_ALIASES.clear()
    _STORY_POOLS.clear()
    _STORY_PERSONS.clear()
    _STORY_CONTEXT.clear()
    _ALIASES_LOADED = True
    pool = "general"
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("#"):
            m = re.match(r"#\s*@pool:\s*(\w+)", ln)
            if m:
                pool = m.group(1).strip().lower()
            continue
        segments = [seg.strip() for seg in ln.split("|")]
        head = segments[0]
        aliases, persons, context = [], [], []
        for seg in segments[1:]:
            kind = seg.split(":", 1)[0].strip().lower() if ":" in seg else ""
            if kind in ("person", "شخص"):
                persons += [v.strip() for v in
                            seg.split(":", 1)[1].split(",") if v.strip()]
                continue
            if kind in ("entity", "كيان", "company"):
                aliases += [v.strip() for v in
                            seg.split(":", 1)[1].split(",") if v.strip()]
                continue
            if kind in ("context", "سياق"):
                context += [v.strip() for v in
                            seg.split(":", 1)[1].split(",") if v.strip()]
                continue
            # legacy untyped segment: comma tokens with subject:/logo:
            for tok in (t.strip() for t in seg.split(",") if t.strip()):
                if tok.lower().startswith("logo:"):
                    _STORY_LOGO_DOMAIN[head] = tok[5:].strip().lower()
                elif tok.lower().startswith("subject:"):
                    _STORY_SUBJECT[head] = tok[8:].strip().lower()
                else:
                    aliases.append(tok)
        # a declared person is also a searchable identity
        if aliases or persons:
            _STORY_ALIASES[head] = persons + aliases
        if persons:
            _STORY_PERSONS[head] = persons
        elif any(seg.split(":", 1)[0].strip().lower()
                 in ("entity", "كيان", "company") for seg in segments[1:]):
            # typed line that declares entities and NO person: the story
            # has no portrait slot at all (the NaDeC Base Nagaoka class)
            _STORY_PERSONS[head] = []
        if context:
            _STORY_CONTEXT[head] = context
        _STORY_POOLS[head] = pool
        stories.append(head)
    global _UNIDENTIFIED_ANNOUNCED
    _UNIDENTIFIED.clear()
    for head in stories:
        if _STORY_POOLS.get(head) != "saudi":
            continue
        if (_STORY_LOGO_DOMAIN.get(head) or _STORY_SUBJECT.get(head)
                or any(a.isascii() for a in _STORY_ALIASES.get(head, []))):
            continue
        _UNIDENTIFIED.add(head)
    if _UNIDENTIFIED and not _UNIDENTIFIED_ANNOUNCED:
        _UNIDENTIFIED_ANNOUNCED = True
        print(f"  ! {len(_UNIDENTIFIED)} saudi entr(y/ies) carry no subject "
              "identity — excluded from selection until fixed:")
        for head in sorted(_UNIDENTIFIED):
            print(f"      - {head[:70]}")
    # duplicate subjects, same one-pass report: siblings retire together
    # on use (by design), but two live lines for one subject mean the
    # chooser can select either — the worklist is to merge or split them
    global _DUPES_ANNOUNCED
    if not _DUPES_ANNOUNCED:
        _DUPES_ANNOUNCED = True
        groups = []
        for head in stories:
            keys = set(_subject_keys(head))
            for g in groups:
                if g["keys"] & keys:
                    g["heads"].append(head)
                    g["keys"] |= keys
                    break
            else:
                groups.append({"keys": keys, "heads": [head]})
        dupes = [g for g in groups if len(g["heads"]) > 1]
        if dupes:
            print(f"  ! {len(dupes)} subject(s) hold more than one line:")
            for g in dupes:
                for h in g["heads"]:
                    print(f"      - {h[:70]}")
    return stories


def story_logo_domain(story):
    """The explicitly declared logo domain for a story line, or ""."""
    if not _ALIASES_LOADED:
        load_stories()
    return _STORY_LOGO_DOMAIN.get(str(story or "").strip(), "")


def resolve_story_input(raw):
    """A manual STORY input becomes a first-class story.

    The box's contents were matched against loaded heads by EXACT string
    equality — five Samsung dispatches missed five ways, and inline
    `| logo:...` tokens the owner typed were silently ignored. Resolution
    order now: exact head -> unique containment match against the loaded
    heads (inheriting the line's declared identity) -> standalone parse of
    any inline `| alias, logo:, subject:` tokens, so what the owner typed
    carries its own identity even for a story that has no line at all.
    """
    raw = (raw or "").strip()
    if not raw:
        return raw
    stories = load_stories()
    if raw in _STORY_POOLS:
        return raw
    head, _, tail = raw.partition("|")
    head = head.strip()
    low = head.casefold()
    cands = [h for h in stories
             if low and (low in h.casefold() or h.casefold() in low)]
    if len(cands) > 1:
        # duplicate-subject siblings resolve to the first; genuinely
        # different lines stay ambiguous and the input is used as typed
        keys = _subject_keys(cands[0])
        if all(_subject_keys(c) & keys for c in cands[1:]):
            cands = cands[:1]
    if len(cands) == 1:
        print(f"    manual story resolved to its stories.txt line: "
              f"{cands[0][:60]}")
        return cands[0]
    if cands:
        print(f"    manual story matches {len(cands)} different lines — "
              "using the input as typed")
    aliases = []
    for tok in (t.strip() for t in tail.split(",") if t.strip()):
        if tok.lower().startswith("logo:"):
            _STORY_LOGO_DOMAIN[head] = tok[5:].strip().lower()
        elif tok.lower().startswith("subject:"):
            _STORY_SUBJECT[head] = tok[8:].strip().lower()
        else:
            aliases.append(tok)
    if aliases:
        _STORY_ALIASES[head] = aliases
    if tail:
        print(f"    manual story carries inline identity: "
              f"aliases={aliases or []}, "
              f"domain={_STORY_LOGO_DOMAIN.get(head, '(none)')}")
    return head


def story_pool(story):
    """The pool a story line belongs to; unknown lines count as general."""
    if not _ALIASES_LOADED:
        load_stories()
    return _STORY_POOLS.get(str(story or "").strip(), "general")


def story_aliases(story):
    """The archive's names for this story's subject, possibly empty."""
    if not _ALIASES_LOADED:
        load_stories()          # a manual STORY env value skips choose_story
    return _STORY_ALIASES.get(str(story or "").strip(), [])


def load_used():
    try:
        data = json.loads(USED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    cutoff = (datetime.now() - timedelta(days=COOLDOWN_DAYS)).isoformat()
    return [e for e in data if e.get("at", "") >= cutoff]


def save_used(previous, story):
    USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    entries = previous + [{"story": story, "at": datetime.now().isoformat()}]
    USED_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    return USED_FILE


# The weekly mix: 4 Saudi-flavour stories and 3 general ones per ISO week.
# The two targets should sum to 7 — one story a day. A skipped day is worse
# than an imperfect ratio (owner's rule), so an exhausted pool borrows from
# the other, loudly, and the count goes to the pool the story actually came
# from. Manual STORY= runs bypass all of this by design.
SAUDI_PER_WEEK = int(os.getenv("SAUDI_PER_WEEK", "").strip() or "4")
GENERAL_PER_WEEK = int(os.getenv("GENERAL_PER_WEEK", "").strip() or "3")
MIX_FILE = Path("state/story_mix.json")


def _iso_week():
    y, w, _ = datetime.now().isocalendar()
    return f"{y}-W{w:02d}"


def load_mix():
    """This week's counts; a new week resets them."""
    week = _iso_week()
    try:
        mix = json.loads(MIX_FILE.read_text(encoding="utf-8"))
    except Exception:
        mix = {}
    if mix.get("week") != week:
        mix = {"week": week, "saudi": 0, "general": 0}
    return mix


def bump_mix(pool):
    mix = load_mix()
    mix[pool] = mix.get(pool, 0) + 1
    MIX_FILE.parent.mkdir(parents=True, exist_ok=True)
    MIX_FILE.write_text(json.dumps(mix, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    commit_and_push(MIX_FILE, f"story mix {ksa_stamp()}")


def choose_pool(mix):
    """Which pool this scheduled run should draw from.

    Furthest behind its target RATIO wins, which spreads the mix through
    the week instead of front-loading one pool; ties go to saudi.
    """
    targets = {"saudi": max(SAUDI_PER_WEEK, 1),
               "general": max(GENERAL_PER_WEEK, 1)}
    behind = {p: mix.get(p, 0) / t for p, t in targets.items()}
    if all(mix.get(p, 0) >= t for p, t in targets.items()):
        print(f"    both pools at weekly target ({mix}) — over-quota run")
    return "saudi" if behind["saudi"] <= behind["general"] else "general"


def _subject_keys(line):
    """Every identity the line's ENTITY answers to: declared domain,
    Latin aliases, or the bare head. Two entries about one subject (a
    Zain story filed under two different lines) must retire together —
    marking one used retires the subject, and equivalence is by key-set
    INTERSECTION, because one sibling may declare a domain the other
    doesn't."""
    keys = set()
    if not _ALIASES_LOADED:
        load_stories()
    subj = _STORY_SUBJECT.get(str(line or "").strip(), "")
    if subj:
        keys.add(subj)
    d = story_logo_domain(line)
    if d:
        keys.add(d)
    keys |= {a.strip().casefold() for a in story_aliases(line)
             if a.isascii()}
    if not keys:
        keys.add(line.split("|")[0].split(":")[0].strip().casefold())
    return keys


def choose_story(exclude=(), pool=None):
    stories = load_stories()
    if not stories:
        return ""
    used = {e["story"] for e in load_used()}
    used |= {e["story"] for e in load_skipped()}
    used |= set(exclude)
    # the preflight's verdicts: a line RECORDED as failing coverage is not
    # eligible — it sits on the curation worklist until the owner adds a
    # logo:domain, drops a curated file, or retires it. Lines the preflight
    # has never seen are not blocked.
    try:
        cov = json.loads(Path("state/story_coverage.json")
                         .read_text("utf-8")).get("entries", {})
        used |= {ln for ln, e in cov.items() if e.get("pass") is False}
    except Exception:
        pass
    used |= _UNIDENTIFIED
    if pool:
        stories = [s for s in stories if _STORY_POOLS.get(s, "general") == pool]
        if not stories:
            return ""
    used_subjects = set()
    try:
        cutoff = (datetime.now()
                  - timedelta(days=SUBJECT_COOLDOWN_DAYS)).isoformat()
        for e in json.loads(USED_FILE.read_text(encoding="utf-8")):
            if e.get("at", "") >= cutoff:
                used_subjects |= _subject_keys(e.get("story", ""))
    except Exception:
        for u in used:
            used_subjects |= _subject_keys(u)
    fresh = [s for s in stories
             if s not in used and not (_subject_keys(s) & used_subjects)]
    if not fresh:
        if pool:
            # never repeat an old story to hold the ratio — the caller
            # borrows from the other pool instead
            return ""
        print("    every story used recently — starting the cycle again")
        fresh = stories
    # Hash the date rather than use the ordinal directly. The ordinal advances
    # by one a day, so consecutive days took consecutive entries — and
    # stories.txt is grouped by section, so a daily story walked straight down
    # one theme: seven businessmen in a row, then seven cities. Invisible at
    # two a week, dominant at one a day. Still deterministic per day, so a
    # retry inside one run picks the same story.
    # readiness preference (owner rule: prefer, NEVER block — a hard
    # block on a NOT READY-heavy pool would starve selection back into
    # consecutive skips): READY first, then THIN and unaudited together,
    # NOT READY last. The pick stays hash-deterministic inside the tier.
    try:
        _cov = json.loads(Path("state/story_coverage.json")
                          .read_text("utf-8")).get("entries", {})
        # LOGO-ONLY is a legitimate deck shape (mark + typographic),
        # not a defect: it shares THIN's tier
        _rank = {"READY": 0, "THIN": 1, "LOGO-ONLY": 1, "NOT READY": 2}
        _best = min(_rank.get(_cov.get(s2, {}).get("readiness"), 1)
                    for s2 in fresh)
        tier = [s2 for s2 in fresh
                if _rank.get(_cov.get(s2, {}).get("readiness"), 1) == _best]
        if tier and len(tier) < len(fresh):
            print(f"    readiness: picking among {len(tier)} "
                  f"{'READY' if _best == 0 else 'THIN/unaudited' if _best == 1 else 'NOT READY'} "
                  "entr(y/ies)")
            fresh = tier
    except Exception:
        pass
    seed = hashlib.md5(datetime.now().date().isoformat().encode()).hexdigest()
    pick = fresh[int(seed, 16) % len(fresh)]
    print(f"    {len(fresh)} of {len(stories)} stories available")
    return pick


def load_skipped():
    """Stories passed over recently because no portrait could be found."""
    try:
        data = json.loads(SKIPPED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    cutoff = (datetime.now() - timedelta(days=STORY_SKIP_DAYS)).isoformat()
    return [e for e in data if e.get("at", "") >= cutoff]


def mark_skipped(story, name, reason="no_portrait"):
    """Remember the miss, so tomorrow's run doesn't spend the same searches
    rediscovering it. One review queue for the owner: the reason code says
    whether it was a missing portrait or a logo-less, mostly-blank deck."""
    SKIPPED_FILE.parent.mkdir(parents=True, exist_ok=True)
    entries = load_skipped() + [{"story": story, "name": name,
                                 "reason": reason,
                                 "at": datetime.now().isoformat()}]
    SKIPPED_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    return SKIPPED_FILE


# The portrait the pre-check verified, cached so the render REUSES it for
# the person frame instead of re-searching. The pre-check and the render
# used to fetch independently: the pre-check verified a real portrait
# existed, then find_photo fetched AGAIN through generic caption-matching
# search — which is how a stranger's face reached the Mrsool hero frame.
_VERIFIED_PORTRAIT = {"name": "", "path": ""}


def find_portrait(name, out_path):
    """A real photograph of this person, or None.

    Commons goes first and matters most: its second lookup is the lead image
    of the person's own article, which is where a portrait actually lives.
    """
    photo, _ = fetch_local_photo([], [name], out_path,
                                 respect_cooldown=False)
    if photo:
        return photo
    photo, _ = fetch_commons_portrait(name, out_path)
    return photo


def pick_story(exclude=()):
    """Choose a story we can actually illustrate.

    Person-led stories are checked for a portrait before anything is spent on
    research. Stories about a company, a city or a product are returned as-is
    — there is no single face to look for, and their pictures are found the
    ordinary way once the frames exist.

    Returns (story, misses).
    """
    tried, misses = list(exclude), 0
    mix = load_mix()
    pool = choose_pool(mix)
    print(f"    weekly mix {mix['week']}: saudi {mix.get('saudi', 0)}"
          f"/{SAUDI_PER_WEEK}, general {mix.get('general', 0)}"
          f"/{GENERAL_PER_WEEK} — drawing from {pool}")
    for _ in range(STORY_ATTEMPTS):
        story = choose_story(exclude=tried, pool=pool)
        if not story:
            other = "general" if pool == "saudi" else "saudi"
            print(f"  ! {pool} pool exhausted this week — drew from {other}")
            pool, story = other, choose_story(exclude=tried, pool=other)
        if not story:
            # both pools dry: fall back to the unrestricted chooser, which
            # may recycle — a skipped day is worse than an imperfect ratio
            story = choose_story(exclude=tried)
        if not story:
            break
        name = person_name(story)
        if not name:
            return story, misses
        print(f"    checking for a portrait of {name}...")
        found = None
        for cand in [name] + story_aliases(story):
            if find_portrait(cand, OUT_DIR / "portrait.jpg"):
                found = cand
                break
        if found:
            if found != name:
                print(f"    portrait resolved via alias: {found}")
            import shutil as _sh
            keep = OUT_DIR / "portrait-verified.jpg"
            _sh.copyfile(OUT_DIR / "portrait.jpg", keep)
            _VERIFIED_PORTRAIT.update(name=found, path=str(keep))
            return story, misses
        print(f"  · no portrait for {name} — trying another story")
        commit_and_push(mark_skipped(story, name), f"no portrait: {name}")
        tried.append(story)
        misses += 1
    return "", misses


def research(story):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    # aliases ride along so image_keywords inherit the searchable name
    aliases = story_aliases(story)
    subject = (f"{story} (أسماء أخرى: {', '.join(aliases)})" if aliases
               else story)
    messages = [{"role": "user", "content": f"القصة: {subject}"}]
    searches = 0
    budget = MAX_TOKENS

    for _ in range(6):
        payload = {
            "model": STORY_MODEL,
            "max_tokens": budget,
            "system": SYSTEM_PROMPT.format(n=STORY_FRAMES),
            "messages": messages,
            "tools": [{"type": "web_search_20250305", "name": "web_search",
                       "max_uses": MAX_SEARCHES}],
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={"content-type": "application/json",
                     "x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01"},
        )
        data = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=600) as resp:
                    data = json.loads(resp.read())
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode()[:400]
                # 429 and 529 (overloaded) are transient: exponential
                # backoff with jitter, four attempts, then give up — a
                # momentary API brownout must not cost a whole run.
                if exc.code in (429, 503, 529) and attempt < 3:
                    import random
                    import time as _t
                    wait = (2 ** (attempt + 1)) + random.uniform(0, 1.5)
                    print(f"  ! Claude API {exc.code} (transient) — "
                          f"backing off {wait:.0f}s ({attempt + 1}/3)")
                    _t.sleep(wait)
                    continue
                raise RuntimeError(f"Claude API {exc.code}: {body}")
            except (TimeoutError, urllib.error.URLError, OSError) as exc:
                # RemoteDisconnected and friends are OSErrors, not
                # HTTPErrors — a dropped socket must not escape unhandled.
                if attempt == 3:
                    raise RuntimeError(
                        f"Claude unreachable after 4 attempts: {exc}")
                print(f"  ! Claude call failed ({exc}) — retrying "
                      f"({attempt + 1}/3)")
                import time as _t
                _t.sleep(8)

        searches += sum(1 for b in data.get("content", [])
                        if b.get("type") == "server_tool_use")

        if data.get("stop_reason") == "pause_turn":
            messages.append({"role": "assistant", "content": data["content"]})
            continue

        # A six-frame story researched by Opus is the longest reply any bot
        # asks for, so it is the one most likely to hit the ceiling. Without
        # this the truncated JSON went straight into json.loads and the run
        # died with a raw traceback, after paying for all the web searches.
        if data.get("stop_reason") == "max_tokens":
            if budget < 32000:
                budget = min(32000, budget * 2)
                print(f"  ! reply truncated — retrying with max_tokens={budget}")
                messages = [{"role": "user",
                             "content": f"القصة: {subject}"}]
                continue
            raise SystemExit(
                "Reply truncated even at 32000 tokens — lower MAX_SEARCHES "
                "or ask for fewer STORY_FRAMES")

        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
        print(f"    {searches} web searches used")
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise SystemExit(f"No JSON in reply: {text[:300]}")
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Reply wasn't valid JSON ({exc}): "
                             f"{text[start:start + 300]}")

    raise SystemExit("Gave up after too many continuations")


PUNCH_GAP = 58          # space above the punch, so it reads as its own beat

# a figure worth setting HUGE on a typographic frame: a number with its
# unit, a percentage, or a four-digit year
_FIGURE_RE = re.compile(
    r"(\d[\d,.]*\s*(?:%|مليار|مليون|ألف|ريال|دولار)|\b(?:1[89]|20)\d{2}\b)")


def _frame_figure(text, punch="", heading=""):
    """The frame's strongest figure, for the typographic treatment.

    Owner decision (2026-08): an interior frame may be typographic — a
    number, a date, a pull line set large where the photo would be — and
    counts as ILLUSTRATED. The figure comes from the frame's own text, so
    it can never be wrong the way a guessed image can.
    """
    for source in (punch or "", text or "", heading or ""):
        m = _FIGURE_RE.search(source)
        if m:
            return m.group(1).strip()
    return ""


def render_frame(path, kicker, counter, big, big_size, sub=None,
                 sub_colour=None, photo=None, footer=None, punch=None):
    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)
    margin, centre, right = 96, W // 2, W - 96
    max_w = W - 2 * margin
    _, kw = ar("م")

    def mid(y, text, font, fill):
        shaped, k = ar(text)
        draw.text((centre, y), shaped, font=font, fill=fill, anchor="ma", **k)

    draw.rectangle([right - 110, 170, right, 180], fill=BRAND_INK)
    shaped, k = ar(kicker)
    draw.text((right, 216), shaped, font=load_font(32, bold=True),
              fill=BRAND_INK, anchor="ra", **k)
    draw_brand_badge(img)
    # the badge holds the corner, so the frame counter tucks in under it
    shaped, k = ar(counter)
    draw.text((margin, 292), shaped, font=load_font(28), fill=MUTED,
              anchor="la", **k)

    y = 420
    pic = None
    if photo:
        try:
            pic = Image.open(photo).convert("RGB")
        except Exception as exc:
            # layout is decided by a successfully-opened image, never by
            # a truthy path: the Samsung SVG deck rendered four bare
            # frames because an unreadable "photo" blocked the designed
            # floor below
            print(f"  ! photo unreadable ({exc}) — taking the designed "
                  "floor instead")
    if pic is not None:
        try:
            box_w, box_h = max_w, int(max_w * 0.72)
            pw, ph = pic.size
            if pw / ph > box_w / box_h:
                new_w = int(ph * box_w / box_h)
                pic = pic.crop(((pw - new_w) // 2, 0,
                                (pw - new_w) // 2 + new_w, ph))
            else:
                pic = pic.crop((0, 0, pw, int(pw * box_h / box_w)))
            pic = pic.resize((box_w, box_h), Image.LANCZOS)
            rounded = _rounded(pic, 36)
            img.paste(rounded, (margin, y), rounded)
            seal_photo(img, margin + box_w, y + box_h)
            y += box_h + 80
        except Exception as exc:
            print(f"  ! couldn't place photo: {exc}")

    size = big_size
    while size > 44:
        f_big = load_font(size, bold=True)
        lines = _wrap(draw, big, f_big, max_w, kw)
        if len(lines) <= (2 if photo else 3):
            break
        size -= 8
    if pic is None:
        # Designed text-only. First choice: the TYPOGRAPHIC treatment —
        # the frame's own strongest figure (a number, a year) set huge in
        # the photo zone; it reads as a deliberate numeric frame and can
        # never be wrong the way a guessed image can. Otherwise the large
        # low-contrast brand watermark keeps the zone composed. Plain
        # centring only if the badge asset is missing too.
        # the heading is the LAST source: the 11am Samsung deck moved its
        # years into headings and every frame lost its numeral — a
        # heading-carried figure still beats an empty photo zone
        figure = _frame_figure(sub, punch, heading=big)
        if figure:
            wm = brand_badge(430, alpha=18)
            if wm is not None:
                img.paste(wm, ((W - 430) // 2, y + 75), wm)
            fig_size = 210
            f_fig = load_font(fig_size, bold=True)
            while fig_size > 90 and draw.textlength(
                    ar(figure)[0], font=f_fig, **kw) > max_w - 80:
                fig_size -= 12
                f_fig = load_font(fig_size, bold=True)
            mid(y + 290 - fig_size // 2, figure, f_fig, TEXT)
            y += 500 + 130
        else:
            wm = brand_badge(500, alpha=30)
            if wm is not None:
                img.paste(wm, ((W - 500) // 2, y + 40), wm)
                y += 500 + 130
            else:
                y = (H - len(lines) * int(size * 1.25)) // 2 - 140
    for line in lines:
        mid(y, line, f_big, TEXT)
        y += int(size * 1.25)

    # The closing seal's band is reserved BEFORE any text is sized — the
    # Mrsool 6/6 frame drew the seal over the punch's last line because the
    # old floor (H-260) sat BELOW the seal's own top edge. The seal is
    # 120px; the band adds breathing room above it, and body/punch flow in
    # the space that remains ABOVE the band, never into it.
    SEAL_SIZE, SEAL_AIR = 120, 36
    seal_centre = (H - 276) if footer else (H - 166)
    bottom = seal_centre - SEAL_SIZE // 2 - SEAL_AIR

    # The punch is the one line on the frame that must not be squeezed, so it
    # is measured before the body and the body gets what is left. Sizing it
    # after the body would let a long paragraph shrink the very line the
    # frame is built around.
    punch = (punch or "").strip()
    punch_lines, f_punch, punch_gap = [], None, 0
    if punch:
        punch_size = 46
        while punch_size > 32:
            f_punch = load_font(punch_size, bold=True)
            punch_lines = _wrap(draw, punch, f_punch, max_w, kw)
            punch_gap = int(punch_size * 1.34)
            if len(punch_lines) <= 2:
                break
            punch_size -= 2
    punch_block = (len(punch_lines) * punch_gap + PUNCH_GAP) if punch_lines else 0

    if sub:
        y += 46
        # longer frames are allowed now, so shrink until the text fits the space
        available = bottom - y - punch_block
        sub_size, line_gap = 42, 60
        while sub_size > 28:
            f_sub = load_font(sub_size, bold=sub_colour == ACCENT)
            lines = _wrap(draw, sub, f_sub, max_w, kw)
            line_gap = int(sub_size * 1.42)
            if len(lines) * line_gap <= available:
                break
            sub_size -= 2
        if len(lines) * line_gap > available:
            # the seal band wins its space; a cramped body is reviewable,
            # an overlapped seal is not — say it loudly for the review pass
            print(f"  ! frame text overflows the seal band even at minimum "
                  f"size ({len(lines)} lines, {available}px available) — "
                  f"REVIEW THIS FRAME")
        for line in lines:
            mid(y, line, f_sub, sub_colour or BODY)
            y += line_gap

    if punch_lines:
        y += PUNCH_GAP
        for line in punch_lines:
            mid(y, line, f_punch, ACCENT)
            y += punch_gap

    # mark 3 sits in its reserved band on EVERY frame — drawn last, after
    # the text that was sized to stay above it
    closing_seal(img, seal_centre)
    if footer:
        f_foot = load_font(26)
        text = footer
        while text and draw.textlength(ar(text)[0], font=f_foot, **kw) > max_w:
            if "، " in text:
                text = text.rsplit("، ", 1)[0]      # drop the last source
            else:
                text = text[:-4]
        mid(H - 160, text, f_foot, MUTED)

    img.save(path, "PNG", optimize=True)
    return path


# words that introduce a name: "شركة X", "جهاز Y", "مدينة Z"
INTRODUCERS = ("شركة", "مؤسسة", "مصنع", "بنك", "متجر", "جهاز", "منتج", "طراز",
               "مدينة", "قرية", "ميناء", "مطار", "جامعة", "مهندس", "مؤسس",
               "رئيس", "مدير", "شريك", "منافس", "علامة", "مشروع", "صندوق",
               "لعبة", "سيارة", "طائرة", "تطبيق", "موقع", "برنامج")


def warn_about_unintroduced_names(brief):
    """Flag proper names dropped into the middle of a story with no
    introduction — a reader meeting 'Fairchild' in frame 3 has lost the thread.

    A name is treated as introduced if an Arabic descriptor sits just before it
    (شركة Fairchild) or if it already appeared earlier. Latin script only;
    Arabic names are left to the prompt.
    """
    frames = brief.get("frames", [])
    seen = set(re.findall(r"\b[A-Z][A-Za-z0-9&.\-]{2,}", brief.get("title", "")))
    ignore = {"The", "And", "For", "USA", "US", "UK", "AI", "TV", "CEO", "GDP"}
    flagged = 0

    for n, frame in enumerate(frames, 1):
        text = f"{frame.get('heading', '')} {frame.get('text', '')}"
        names = set(re.findall(r"\b[A-Z][A-Za-z0-9&.\-]{2,}", text)) - ignore

        for name in sorted(names - seen):
            if n == 1:
                continue
            # is it introduced right here?
            window = text[max(0, text.find(name) - 24):text.find(name)]
            if any(word in window for word in INTRODUCERS):
                continue
            flagged += 1
            print(f"  ? {name} appears in frame {n} with no introduction — "
                  "the previous frame should hand it over")
        seen |= names

    if not flagged and len(frames) > 1:
        print("    handshakes: every name is introduced before use")


def warn_about_misplaced_hooks(brief):
    """Frame 1 of the Samsung deck (1938, a dried-fish merchant) wore
    «150 ألف جهاز احترقت في يوم واحد» — frame 4's 1995 event hoisted
    forward as a teaser. A heading describes its own frame: any number
    in a heading that is absent from the frame's own text but present in
    another frame's text is a hoisted hook."""
    frames = brief.get("frames", [])
    flagged = 0
    for n, frame in enumerate(frames, 1):
        heading = str(frame.get("heading", ""))
        body = f"{frame.get('text', '')} {frame.get('punch', '')}"
        for num in sorted(set(re.findall(r"\d[\d,.]*", heading))):
            if num in body:
                continue
            others = [m for m, fr in enumerate(frames, 1) if m != n
                      and num in f"{fr.get('text', '')} "
                                 f"{fr.get('punch', '')}"]
            if others:
                flagged += 1
                print(f"  ? frame {n} heading carries «{num}», which "
                      f"belongs to frame {others[0]} — a hoisted hook; "
                      "the hook stays on its own frame")
    if not flagged and frames:
        print("    hooks: every heading describes its own frame")


def build_frames(brief, stamp, photos):
    """Render one frame per beat. The last frame carries the sources."""
    frames = brief.get("frames", [])[:STORY_FRAMES]
    if len(frames) < 4:
        raise SystemExit(f"expected at least 4 frames, got {len(frames)}")

    if len(photos) < len(frames):
        raise SystemExit(f"{len(frames)} frames but only {len(photos)} photos")

    # source names only — a raw URL in the footer looks like a mistake
    names = []
    for src in brief.get("sources", [])[:3]:
        src = str(src).strip()
        # a bare URL: keep the domain, dropping the scheme and the path
        m = re.match(r"https?://(?:www\.)?([^/\s]+)", src)
        if m:
            src = m.group(1)
        else:
            # "The revival of AlUla's Old Town: courier.unesco.org" -> domain
            tail = src.split(":")[-1].strip()
            if ":" in src and re.search(r"[a-z]+\.[a-z]{2,}", tail):
                src = tail
        src = src.rstrip(" .،-").strip()
        if len(src) > 28:                    # still a sentence — keep it short
            src = src[:28].rsplit(" ", 1)[0].rstrip(" .،-")
        if src:
            names.append(src)
    sources = "، ".join(dict.fromkeys(names))
    total = len(frames)
    paths = []

    for n, frame in enumerate(frames, 1):
        last = n == total
        punch = (frame.get("punch") or "").strip()
        # the opening frame leads with the story title, the rest with their beat
        heading = brief["title"] if n == 1 else frame.get("heading", "")
        # The closing frame is normally red throughout. If it also carries a
        # punch, the body goes back to ordinary ink so the red still marks one
        # line — a frame that is entirely red emphasises nothing.
        foot = (f"المصدر: {sources}" if sources else None) if last else None
        photo = photos[n - 1]
        if photo and Path(str(photo) + ".generated").exists():
            # rule 2: a generated image is never unlabelled
            foot = f"{foot} • {GENERATED_CREDIT}" if foot else GENERATED_CREDIT
        paths.append(render_frame(
            OUT_DIR / f"{stamp}-story-{n:02d}.png", BRAND,
            f"{n} / {total}",
            heading, 60, sub=frame.get("text", ""),
            sub_colour=ACCENT if (last and not punch) else None,
            photo=photo, punch=punch, footer=foot))

    return [str(p) for p in paths]



def _person_frame_photo(frame, out_path, seen):
    """A photo for a frame whose text NAMES a person — identity first.

    Only provenance that verifies WHO is in the picture is allowed here:
    the pre-check's cached portrait, the owner's local library, and
    fetch_commons_portrait (article-lead or name-in-FILE-TITLE search).
    Generic keyword search is forbidden on person frames — captions
    matching a name is exactly how a stranger's face was captioned as
    Mrsool's founder. The Commons route's results DO pass the vision
    gate now: the old exemption ("a verified portrait of the named
    person is definitionally right") rode on every keyword naming a
    person, and the model put 'Hotel Okura Tokyo' on a person frame —
    the article-lead route returned the hotel's 2019 glass tower
    stamped as a portrait, exempt from the one check whose era clause
    was written for exactly that picture. Identity provenance is
    unchanged; the gate is a veto on top, never a widening.
    """
    import shutil as _sh
    keywords = [k for k in (frame.get("image_keywords") or []) if k]
    keywords_ar = [k for k in (frame.get("image_keywords_ar") or []) if k]
    hay = " ".join(keywords + keywords_ar + [frame.get("text", "")]).lower()

    # the portrait the pre-check already verified, if this frame names them
    cached = _VERIFIED_PORTRAIT
    if cached["path"] and Path(cached["path"]).exists():
        name_l = cached["name"].lower()
        if name_l and (name_l in hay
                       or any(name_l in k.lower() for k in keywords)):
            if not any(same_picture(_photo_digest(cached["path"]), s0)
                       for s0 in seen):
                _sh.copyfile(cached["path"], out_path)
                print("    person frame: reusing the pre-check's verified "
                      f"portrait of {cached['name']}")
                return str(out_path)

    def fresh(photo):
        d = _photo_digest(photo)
        return not any(same_picture(d, s0) for s0 in seen)

    context = (f"{frame.get('heading', '')}\n"
               f"{frame.get('text', '')}").strip()
    for kw in keywords + keywords_ar:
        photo, _ = fetch_local_photo([kw], [kw], out_path,
                                     respect_cooldown=False)
        if photo and fresh(photo):
            return photo
        photo, _ = fetch_commons_portrait(kw, out_path)
        if photo and fresh(photo):
            if photo_shows(photo, context) != "yes":
                # a NEUTRAL portrait is not a portrait: محايدة means the
                # picture does not show the person — File:FruitColors.jpg
                # shipped as a farmer's face through that gap
                print(f"    person frame: gate did not confirm the "
                      f"'{kw}' result — right route, unproven picture")
                continue
            return photo
    return None


def find_photo(spec, out_path, seen=(), context="", allow_neutral=True,
               bank=None):
    """One photo for one frame, searched by subject.

    Any real photograph about the story serves — the person, the product, the
    building, the logo. A single keyword match is enough here, because we are
    searching for a subject rather than matching a described scene.

    Anything already used elsewhere in this story is refused and the search
    carries on: the same picture on two frames of one series reads as a
    mistake, and the reader notices it before they notice the text.
    """
    # Neutrals are BANKED, never settled here. "First banked neutral" used
    # to be copied into the slot as soon as this pass ended, which made it
    # the de-facto selector: it pre-empted widening, the curated logo and
    # the repeat, and a modern aerial shipped while the protagonist's own
    # 1938 portrait sat in hand. find_all_photos owns the ladder now; this
    # function returns a yes or nothing, and hands the bank back tiered by
    # which keyword found each candidate — a frame's own Latin keyword
    # (tier 0, most specific) beats its own Arabic (tier 1); within a tier,
    # first found wins.
    # Stale cleanup only when this pass may bank: the widening pass
    # (allow_neutral=False) runs on the same slot AFTER the own-keyword pass,
    # and cleaning here destroyed the bank rung 4 was about to use — the
    # drill caught the neutral file vanishing between rungs.
    if allow_neutral:
        for stale in Path(out_path).parent.glob(
                Path(out_path).name + ".neutral*"):
            stale.unlink()
    bank_local = {}

    def take(result, tier=0):
        photo = result[0] if isinstance(result, tuple) else result
        if not photo:
            return None
        d = _photo_digest(photo)
        if any(same_picture(d, s0) for s0 in seen):
            print("      (that picture is already on an earlier frame "
                  "— looking further)")
            return None
        if not context:
            return photo
        verdict = photo_shows(photo, context)
        if verdict == "yes":
            return photo
        # Widened searches must not bank neutrals at all: story-level
        # fallback plus a generic Arabic single («صحراء») once pulled a
        # Tunisian tourism photo onto a Saudi story.
        if allow_neutral and verdict == "neutral" and tier not in bank_local:
            import shutil as _sh
            kept = Path(f"{out_path}.neutral{tier}")
            _sh.copyfile(photo, kept)         # later fetches overwrite out_path
            bank_local[tier] = kept
        return None

    def settle(photo):
        """A yes wins outright; otherwise report the bank and return None."""
        if photo is not None:
            for kept in bank_local.values():
                kept.unlink(missing_ok=True)
            return photo
        if bank is not None:
            bank.extend(sorted(bank_local.items()))
        return None

    keywords = [k for k in (spec.get("image_keywords") or []) if k]
    if not keywords:
        keywords = spec.get("image_queries") or []
    keywords_ar = [k for k in (spec.get("image_keywords_ar") or []) if k]

    # The library rung walks its RANKED candidates through the gate.
    # One best-scored offer used to be the library's whole say: the
    # coffee deck's dallah (top score, wrong angle) eclipsed the harvest
    # photo the farming frames were asking for — six gate rejections,
    # six blank frames, a skipped story with the right seed on disk.
    photo, tried_local = None, []
    for _ in range(6):     # a 5-seed subject needs the walk to reach them all
        cand, _lc = fetch_local_photo([], keywords, out_path,
                                      exclude=tried_local)
        if not cand:
            break
        d0 = _photo_digest(cand)
        if any(same_picture(d0, s0) for s0 in seen):
            photo = None
        else:
            v = photo_shows(cand, context) if context else "yes"
            # the OWNER curated this file for this beat: a real,
            # subject-bound photo that merely proves nothing (محايدة)
            # still beats a blank frame — only an actively misleading
            # لا refuses a seed
            photo = cand if v in ("yes", "neutral") else None
        if photo:
            break
        try:
            marker = Path(str(out_path) + ".exempt").read_text("utf-8")
            tried_local.append(marker.split(":", 1)[1].strip())
        except Exception:
            break

    # SPA before Commons: the official Saudi archive is the likeliest holder
    # of modern Saudi corporate frames (the Aramco Tadawul-listing frame is
    # exactly SPA material) and is already licensed for this project. One
    # call with the whole Arabic list, mirroring news_bot's call site — the
    # fetcher iterates phrase-then-words internally, so this IS the
    # per-keyword narrowest-first shape, with one quiet log line when the
    # archive has nothing. Saudi state media holds nothing on foreign
    # subjects; no language detection — having Arabic keywords at all is the
    # only signal (the widened pass carries the story-level image_queries_ar
    # in as keywords_ar, so that case is covered too).
    if photo is None and keywords_ar:
        photo = take(fetch_spa_photo(keywords_ar, out_path), tier=1)

    # Commons and LoC come BEFORE Openverse: historical Saudi subjects are
    # their territory, and the correct Steineke photo Openverse surfaced was
    # itself Wikimedia-hosted. Same one-keyword-at-a-time shape as the
    # Openverse loops below; the credit each returns is dropped by take(),
    # exactly as it already is for Openverse frames.
    for keyword in keywords:
        if photo:
            break
        photo = take(fetch_commons_photo([keyword], out_path, need_saudi=False,
                                         min_hits=1, subject_mode=True))
    for keyword in keywords_ar:
        if photo:
            break
        photo = take(fetch_commons_photo([keyword], out_path, need_saudi=False,
                                         min_hits=1, subject_mode=True), tier=1)
    # LoC is an English-language archive — Arabic keywords would be wasted
    for keyword in keywords:
        if photo:
            break
        photo = take(fetch_loc_photo([keyword], out_path, need_saudi=False,
                                     min_hits=1, subject_mode=True))

    # try each keyword on its own — "Steve Jobs" finds more than a long phrase
    for keyword in keywords:
        if photo:
            break
        photo = take(fetch_openverse_photo([keyword], out_path, need_saudi=False,
                                           min_hits=1, subject_mode=True))

    # Openverse indexes Arabic titles and tags too, and a Saudi subject is
    # often catalogued only in Arabic — so the Latin pass can come back empty
    # on a story that does have pictures. Worth asking in Arabic before
    # settling for generated filler or a repeat.
    for keyword in keywords_ar:
        if photo:
            break
        photo = take(fetch_openverse_photo([keyword], out_path, need_saudi=False,
                                           min_hits=1, subject_mode=True), tier=1)

    # generation is not a search result: it lives in find_all_photos'
    # kind ladder, reachable only from abstract frames
    return settle(photo)


LOGOS_DIR = Path(os.getenv("LOGOS_DIR", "images/logos"))
FLAGS_DIR = Path(os.getenv("FLAGS_DIR", "images/flags"))
# Country names as they appear in frame keywords/headings, mapped to the
# ISO-3166 filename in images/flags/. Curated and small on purpose: a name
# missing here just means the country frame falls to its text-only floor.
# Cities never borrow their country's flag — the map holds countries only.
_COUNTRY_ISO = {
    "السعودية": "sa", "saudi": "sa",
    "الصين": "cn", "china": "cn", "chinese": "cn",
    "أمريكا": "us", "الولايات المتحدة": "us", "united states": "us",
    "اليابان": "jp", "japan": "jp",
    "الهند": "in", "india": "in",
    "بريطانيا": "gb", "المملكة المتحدة": "gb", "britain": "gb",
    "الإمارات": "ae", "uae": "ae", "emirates": "ae",
    "مصر": "eg", "egypt": "eg",
    "كوريا": "kr", "korea": "kr",
    "ألمانيا": "de", "germany": "de",
    "فرنسا": "fr", "france": "fr",
    "سنغافورة": "sg", "singapore": "sg",
}


def _letterbox_graphic(src, dest):
    """Compose a flat graphic (logo, flag) onto a cream canvas shaped like
    the photo box, so the renderer's crop-to-fill changes nothing."""
    from PIL import Image as _Im
    img = _Im.open(src).convert("RGBA")
    BOX_W, BOX_H = 888, 639
    canvas = _Im.new("RGB", (BOX_W * 2, BOX_H * 2), BG_TOP)
    scale = min(canvas.width * 0.78 / img.width,
                canvas.height * 0.78 / img.height)
    scaled = img.resize((max(1, int(img.width * scale)),
                         max(1, int(img.height * scale))), _Im.LANCZOS)
    canvas.paste(scaled, ((canvas.width - scaled.width) // 2,
                          (canvas.height - scaled.height) // 2), scaled)
    canvas.save(dest, "JPEG", quality=92)
    # provenance carve-out, same as curated logos: a flag IS a flat graphic
    # by design, so it never meets the pixel check or the vision gate, and
    # it repeats across stories by design — exempt from the cooldown
    Path(str(dest) + ".exempt").write_text("curated", encoding="utf-8")
    return str(dest)


def _curated_flag(frame_no, frame):
    """images/flags/<iso>.png for a place_country frame, or None."""
    hay = " ".join(filter(None, [
        str(frame.get("heading", "")),
        " ".join(frame.get("image_keywords") or []),
        " ".join(frame.get("image_keywords_ar") or []),
    ])).lower()
    for name, iso in _COUNTRY_ISO.items():
        if name in hay:
            src = FLAGS_DIR / f"{iso}.png"
            if not src.exists():
                print(f"    frame {frame_no}: no flag on file for "
                      f"{iso} — falling through")
                return None
            dest = OUT_DIR / f"story-frame-{frame_no}.jpg"
            print(f"    frame {frame_no}: using curated flag {src}")
            return _letterbox_graphic(src, dest)
    return None


def _generated_frame(frame, slot):
    """Gated, labelled generation — the abstract kind's last rung before
    text-only. fetch_generated_photo carries the whole defence: prompt
    scrub, the vision gate (text/faces/currency/flags/maps), one retry,
    clean give-up, and the .generated marker the renderer labels from."""
    if not ALLOW_STORY_GENERATION:
        return None
    subject = ((frame.get("image_keywords") or [""])[0]
               or frame.get("heading", ""))
    prompt = (f"A plain, unbranded photograph relating to {subject}. "
              "No buildings with signs, no offices, no logos, no text, "
              "no faces, no flags, no country-identifying features, no maps.")
    photo, _ = fetch_generated_photo(prompt, slot)
    return photo
# Owner's policy, decided 2026-08: showing a company's CURRENT logo when
# covering that company is ordinary editorial imagery — the bot may fetch
# and cache it without per-company approval. Historical/era marks stay
# manual: no mechanism can verify a file labelled 1938 is the 1938 mark.
# Empty-string fallback as everywhere — GitHub passes "" for unset vars.
LOGO_AUTO_CURRENT = (os.getenv("LOGO_AUTO_CURRENT", "").strip() or "1") == "1"


def _logo_slug(name):
    """Deterministic, collision-safe-enough slug from a subject keyword:
    lowercase, punctuation stripped, spaces to hyphens. If two companies
    ever collide, first-writer-wins — acceptable at ~400 stories, and not
    worth engineering around."""
    s = re.sub(r"[^\w\s-]", "", name.strip().lower())
    return re.sub(r"[\s_]+", "-", s).strip("-")


def _auto_current_logo(brief, frame, frame_no):
    """Fetch + cache the subject's current logo — domain-declared only.

    The domain comes from an explicit `| logo:domain.com` field on the
    stories.txt line; it is the identity AND the cache key. No domain, no
    fetch — deriving a slug from display keywords is how a wrong company's
    mark gets guessed onto a story. The matched article must reference the
    domain, so the title-verified file provably belongs to the declared
    company.
    """
    domain = story_logo_domain(brief.get("story", ""))
    if not domain:
        print(f"    frame {frame_no}: no `logo:` domain declared for this "
              "story — auto-fetch is off (curated files still match)")
        return None
    dest = LOGOS_DIR / f"{domain}-current.png"
    if dest.exists():
        return dest
    # The lookup names are the DECLARED identity: the line's own aliases.
    # They were the model's image_keywords once, and the model emits search
    # phrases ('Samsung Electronics 1938 grocery store') whose every word
    # the title-verification then demands — no article matches, the fetch
    # returns nothing, and the deck ships logo-less while the domain sat
    # there correct the whole time. Traced live on the Samsung run.
    line = str(brief.get("story", ""))
    names = [a for a in story_aliases(line) if a.isascii()]
    title = str(brief.get("title", "")) + " " + line
    names += [a for a in story_aliases(line)
              if not a.isascii() and a in title]
    if not names:
        print(f"    frame {frame_no}: logo domain {domain} declared but the "
              "line has no alias to search the article by")
        return None
    try:
        from logo_fetch import fetch_current, update_index
    except ImportError as exc:
        print(f"    ! logo self-fill unavailable ({exc})")
        return None
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        got = fetch_current(domain, names, require_domain=domain)
    except Exception as exc:
        print(f"    ! current-logo fetch failed for {domain}: {exc}")
        got = None
    if not got:
        # a story must never die on a logo — fall through to text-only
        print(f"    frame {frame_no}: no fetchable current logo for {domain}")
        return None
    update_index(domain, names + [domain])
    commit_and_push(LOGOS_DIR, f"curated logo: {domain}-current (auto)")
    print(f"    frame {frame_no}: fetched + cached current logo for {domain}")
    return Path(got)


def _curated_logo(frame_no, total, brief, frame, allow_hero=False):
    """An era-matched curated logo for this frame, or None.

    Deliberate editorial fallback, not photography: rule 3 rejects logo cards
    that ARRIVE FROM ARCHIVE SEARCH (filler on a news card), and that pixel
    check is untouched — files never enter through it here. Provenance is the
    carve-out: only files sitting in images/logos/, placed there by the owner
    (renaming a reviewed candidate into the folder is the approval step), are
    eligible. The vision gate is skipped for the same reason — it would say
    "not a real photograph", which is true and beside the point.
    """
    if frame_no == 2 and not allow_hero:
        # the protagonist frame shows a face, never a logo — EXCEPT when the
        # person ladder itself asks, having found no verified portrait:
        # then the logo is the honest fallback (Mrsool incident)
        return None
    try:
        files = sorted(LOGOS_DIR.glob("*.png"))
    except OSError:
        files = []

    # The story's SUBJECT identity — names, not a keyword haystack. The
    # old matcher checked every alias as a SUBSTRING of all the story's
    # keywords, and one poisoned alias («جدة», stored as a "name" for
    # Savola because it was Savola's first Arabic search term) put the
    # SAVOLA logo on the Jameel/Toyota story: any Jeddah story matched a
    # food company. A logo may only ever belong to the story's own
    # subject, so matching is exact identity now: the file's slug or one
    # of its index aliases must EQUAL a declared subject name (story-level
    # keywords or the stories.txt aliases) — never merely appear inside
    # the keyword soup.
    subject_names = [k for k in (brief.get("image_keywords") or []) if k][:3]
    subject_names += story_aliases(str(brief.get("story", "")))
    subject_names = [n for n in dict.fromkeys(subject_names) if n]
    subject_slugs = {_logo_slug(n) for n in subject_names if _logo_slug(n)}
    subject_lc = {n.strip().casefold() for n in subject_names}
    domain = story_logo_domain(brief.get("story", ""))
    if domain:
        subject_slugs.add(domain)
        subject_lc.add(domain)

    try:
        aliases = json.loads((LOGOS_DIR / "index.json").read_text("utf-8"))
    except Exception:
        aliases = {}

    candidates = {}                       # slug -> [(era_key, path)]
    for f in files:
        stem = f.stem
        if "-" not in stem:
            continue
        slug, era = stem.rsplit("-", 1)
        file_names = aliases.get(slug, [])
        if not (slug in subject_slugs
                or any(a.strip().casefold() in subject_lc
                       for a in file_names)
                or any(_logo_slug(a) in subject_slugs for a in file_names)):
            continue
        key = float("inf") if era == "current" else             int(era) if era.isdigit() and len(era) == 4 else None
        if key is None:
            continue
        candidates.setdefault(slug, []).append((key, f))
    if not candidates and LOGO_AUTO_CURRENT:
        fetched = _auto_current_logo(brief, frame, frame_no)
        if fetched is not None:
            candidates = {fetched.stem.rsplit("-", 1)[0]:
                          [(float("inf"), fetched)]}
    if not candidates:
        return None

    eras = sorted(next(iter(candidates.values())))
    # ERA MATCHING IS MANDATORY (owner rule): a current mark must never sit
    # on a frame set decades earlier. The frame's own text names its year;
    # when it does, pick the nearest era file — and if only "current"
    # exists for a frame >=20 years back, refuse: the typographic frame is
    # always preferable to an anachronism.
    m = re.search(r"\b(1[89]\d\d|20[0-2]\d)\b",
                  str(frame.get("text", "")) + " "
                  + str(frame.get("heading", "")))
    frame_year = int(m.group(1)) if m else None
    if frame_year is not None:
        this_year = datetime.now().year
        dated = [(k, p2) for k, p2 in eras if k != float("inf")]
        if dated:
            key, path = min(dated, key=lambda e: abs(e[0] - frame_year))
            if abs(key - frame_year) > 25 and this_year - frame_year >= 20:
                print(f"    frame {frame_no}: nearest era mark ({int(key)}) "
                      f"is {abs(int(key) - frame_year)}y off a {frame_year} "
                      "frame — refusing, typographic beats an anachronism")
                return None
        elif this_year - frame_year >= 20:
            print(f"    frame {frame_no}: only a CURRENT mark exists for a "
                  f"{frame_year} frame — refusing, typographic beats an "
                  "anachronism")
            return None
        else:
            _, path = eras[-1]
    elif len(eras) == 1:
        _, path = eras[0]
    elif frame_no == 1:
        _, path = eras[0]
    elif frame_no == total:
        _, path = eras[-1]
    else:
        idx = round((frame_no - 1) / max(total - 1, 1) * (len(eras) - 1))
        _, path = eras[idx]

    tag = ("opening frame" if frame_no == 1 else
           "closing frame" if frame_no == total else f"frame {frame_no}")
    dest = OUT_DIR / f"story-frame-{frame_no}.jpg"
    from PIL import Image as _Im
    img = _Im.open(path).convert("RGBA")
    # The renderer CROPS photos to fill its box — right for photography,
    # fatal for a wordmark (the real aramco-current.png is 3840x1081; a
    # crop-to-fill would slice both ends off the name). Letterbox instead:
    # compose the logo at ~78% width onto a cream canvas already shaped
    # like the box, so the renderer's crop changes nothing.
    BOX_W, BOX_H = 888, 639
    canvas = _Im.new("RGB", (BOX_W * 2, BOX_H * 2), BG_TOP)
    scale = min(canvas.width * 0.78 / img.width,
                canvas.height * 0.78 / img.height)
    logo = img.resize((max(1, int(img.width * scale)),
                       max(1, int(img.height * scale))), _Im.LANCZOS)
    canvas.paste(logo, ((canvas.width - logo.width) // 2,
                        (canvas.height - logo.height) // 2), logo)
    canvas.save(dest, "JPEG", quality=92)
    # curated logos repeat by design — exempt from the cross-run cooldown
    Path(str(dest) + ".exempt").write_text("logo", encoding="utf-8")
    print(f"    frame {frame_no}: logo {path} for story slug(s) "
          f"{sorted(subject_slugs) or ['(auto)']} (era match: {tag})")
    return str(dest)

# at most this many frames may carry the subject's logo — the owner's
# rule after a deck papered 4/6 frames with one mark
LOGO_MAX_FRAMES = int(os.getenv("LOGO_MAX_FRAMES", "").strip() or "2")
# more blank frames than this and the deck is skipped, not shipped —
# "don't ship a mostly-empty deck", not "skip on a single gap"
STORY_MAX_BLANK_FRAMES = int(
    os.getenv("STORY_MAX_BLANK_FRAMES", "").strip() or "2")
_LAST_SKIP = ""


def find_all_photos(brief):
    """A picture for a frame that has one; a text-only frame otherwise.

    The owner's inversion (2026-08): a photo is NOT required on every
    frame — the writing carries a frame alone. Per frame: the frame's OWN
    keywords, relevance-verified, then the kind-specific mark (subject
    logo / flag / gated generation), then TEXT-ONLY as a first-class
    floor. The widened story-subject pass, the neutral bank, the
    recent-photo rescue and the in-story repeat are gone — each existed
    to scrape up "some photo", and decks came back with sponsor stadiums
    and triplicate skylines instead of honest bare frames.
    """
    global _LAST_SKIP
    frames = brief.get("frames", [])[:STORY_FRAMES]
    # story-level Arabic names, the backstop for a frame with a MISSING
    # Arabic list (an explicit [] is an answer) — still the story's own
    # vocabulary, not a widening to another subject
    fallback_ar = [k for k in (brief.get("image_queries_ar") or [])
                   if k][:3]
    # the general-photo pool: story subject terms, with person-frame names
    # stripped — identity is not subject to widening (Mrsool incident)
    person_kws = {k.lower() for f in frames
                  if (f.get("subject_kind") or "").strip().lower() == "person"
                  for k in ((f.get("image_keywords") or [])
                            + (f.get("image_keywords_ar") or [])) if k}
    fallback = list(brief.get("image_keywords", []))
    for frame in frames[1:2] + frames[0:1]:
        if (frame.get("subject_kind") or "").strip().lower() == "person":
            continue
        fallback += [k for k in (frame.get("image_keywords") or []) if k][:2]
    # Dominant story kind: a story with any company/product frame is a
    # COMPANY story (logo-primary, tight search); one with none is
    # HISTORICAL/ABSTRACT — an event, era or concept whose correct primary
    # visual is archival photography, where "no logo" is expected and must
    # not drive the skip. The bourse story (Amsterdam, 1602) skipped as
    # "logo unavailable" — wrong failure class entirely.
    kinds_all = [(f.get("subject_kind") or "abstract").strip().lower()
                 for f in frames]
    story_has_company = any(k in ("company", "product") for k in kinds_all)
    # IMAGE-SUBJECT BINDING (owner rule, after a Riyadh Air aircraft
    # shipped in a Zain licensing story): on a company story, every image
    # query is scoped to the DECLARED subject entity — never built from an
    # individual frame's text, where background entities lurk. One correct
    # subject image is enough; typographic frames carry the rest.
    subject_line = str(brief.get("story", ""))
    subj_lat = [a for a in story_aliases(subject_line) if a.isascii()]
    subj_ar = [a for a in story_aliases(subject_line) if not a.isascii()]
    if not subj_lat:
        subj_lat = [k for k in (brief.get("image_keywords") or []) if k][:1]
    subject_name = (subj_lat or subj_ar or [""])[0]
    subject_spec = {"image_keywords": subj_lat[:2],
                    "image_keywords_ar": subj_ar[:2]}
    if story_has_company and not subject_name:
        # binding is on and there is nothing to bind to: frame keywords
        # are ignored by design, so this story cannot be illustrated —
        # skip it loudly instead of discovering that mid-run
        print("  ! company story with NO declared subject — skipping "
              "(add aliases / subject: / logo: to its stories.txt line)")
        _LAST_SKIP = "no subject declared on the stories.txt line"
        return None
    if story_has_company:
        print(f"    image queries bound to subject: {subject_name}")
    if not story_has_company:
        print("    story kind: historical/abstract — archival photos are "
              "the primary visual; the logo rung is N/A")
    fallback = [k for k in dict.fromkeys(fallback)
                if k and k.lower() not in person_kws
                ][:5 if not story_has_company else 3]
    fallback_ar = [k for k in fallback_ar if k.lower() not in person_kws]
    photos = []
    used = set()                      # digests of pictures already in the story
    # one mark papering most of a deck is a fail, not a pass (owner rule:
    # the same logo on 4/6 frames reads as filler) — beyond the cap the
    # frame takes the designed text-only treatment instead. Frame NUMBERS,
    # not a count: placement discipline needs to know WHERE the marks sit.
    logo_slots = []
    for n, frame in enumerate(frames, 1):
        spec = dict(frame)
        # An explicit [] is an answer, not a gap: the prompt asks for it when
        # a beat is purely foreign, and forcing the story's Arabic keywords
        # onto such a frame is how you attach a Saudi photo to a beat about
        # Fairchild. Only a missing field falls back.
        own_ar = frame.get("image_keywords_ar")
        spec["image_keywords_ar"] = (fallback_ar if own_ar is None
                                     else [k for k in own_ar if k])
        keywords = [k for k in (spec.get("image_keywords") or []) if k]
        if story_has_company:
            print(f"    frame {n}: (queries bound to subject — frame "
                  f"keywords ignored)")
        else:
            line = ", ".join(keywords[:4]) or "(no keywords)"
            if spec["image_keywords_ar"]:
                line += f"  |  {', '.join(spec['image_keywords_ar'][:3])}"
            print(f"    frame {n}: {line}")

        context = f"{frame.get('heading', '')}\n{frame.get('text', '')}".strip()
        slot = OUT_DIR / f"story-frame-{n}.jpg"
        # The ladder is keyed by what the MODEL says the frame is about —
        # an unsure model writes "abstract". Order per the owner's revision
        # after the blank-deck incident: a WRONG photo is worse than a
        # logo, but a bare beige frame is a scroll-past — so the subject's
        # logo is the PRIMARY fallback, an on-topic general photo next,
        # and text-only is the LAST resort, not the default.
        kind = (frame.get("subject_kind") or "abstract").strip().lower()
        tier = None
        photo = None          # every rung below may only FILL, never assume

        bank = []
        if kind == "person":
            # identity first, always: verified portrait or no face at all
            photo = _person_frame_photo(frame, slot, used)
            if photo:
                tier = "verified portrait"
        else:
            # asset priority, cheapest and safest first (owner rule): on a
            # company story the BRAND MARK leads — deterministic identity,
            # zero search risk — with the era rule inside refusing any
            # anachronistic placement; photos come second
            if story_has_company and photo is None \
                    and len(logo_slots) < LOGO_MAX_FRAMES:
                # placement discipline (owner rules, Samsung 5+6 deck):
                # two identical marks on consecutive frames read as
                # filler, so a second mark needs a gap; and the closing
                # frame is NOT a preferred slot — it takes a mark only
                # when the deck would otherwise carry none. The cap is a
                # ceiling, not a target: one well-placed mark beats two
                # crowded ones.
                adjacent = bool(logo_slots) and n - logo_slots[-1] < 2
                closing_second = n == len(frames) and bool(logo_slots)
                if adjacent:
                    print(f"    frame {n}: logo slot refused — adjacent "
                          f"to frame {logo_slots[-1]}'s mark")
                elif closing_second:
                    print(f"    frame {n}: logo slot refused — closing "
                          f"frame, deck already marked on frame "
                          f"{logo_slots[-1]}")
                else:
                    lead = _curated_logo(n, len(frames), brief, frame,
                                         allow_hero=True)
                    if lead is not None:
                        photo, tier = lead, "subject logo"
                        logo_slots.append(n)
            if story_has_company:
                # frame keywords are ignored by design: the query IS the
                # subject, and the gate hears the subject too
                spec = dict(spec, **subject_spec)
                context = f"القصة عن {subject_name}.\n{context}"
            # Historical stories BANK neutrals: a period photo of the
            # story's world that doesn't show this beat's exact subject is
            # precisely the right archival fallback for a 1602 frame — the
            # bank was removed because COMPANY decks abused it (sponsor
            # stadiums), so it returns kind-aware: no-company stories only.
            if photo is None:
                photo = find_photo(spec, slot, used, context,
                                   allow_neutral=not story_has_company,
                                   bank=bank if not story_has_company else None)
            if photo and tier is None:
                tier = "relevant photo"

        # country frames keep their flag ahead of the logo
        if photo is None and kind == "place_country":
            flag = _curated_flag(n, frame)
            if flag is not None:
                photo, tier = flag, "curated flag"

        # THE primary fallback on COMPANY stories: the subject's own logo
        # (curated or auto-fetched, never a sponsor's) — every kind, person
        # frames included. Historical stories never consult it: there is
        # no subject logo to fetch, and the auto-slug would go hunting a
        # modern namesake's mark for a 1602 story.
        if photo is None and story_has_company \
                and len(logo_slots) >= LOGO_MAX_FRAMES:
            print(f"    frame {n}: logo cap reached ({LOGO_MAX_FRAMES}) "
                  "— photos or typographic carry the rest")

        # general on-topic photo, gate-verified against this frame's text —
        # never for person frames (identity is not subject to widening)
        if photo is None and kind != "person" and fallback \
                and not story_has_company:
            print(f"      widening to the story subject: "
                  f"{', '.join(fallback)}")
            photo = find_photo({"image_keywords": fallback,
                                "image_keywords_ar": fallback_ar},
                               slot, used, context, allow_neutral=False)
            if photo:
                tier = "general photo (last resort)"

        # historical stories: the banked archival neutral carries the
        # frame before text-only — a real period photograph of the story's
        # world, tiered by which of the frame's own keywords found it
        if photo is None and bank:
            btier, kept = bank[0]
            import shutil as _sh
            _sh.copyfile(kept, slot)
            photo, tier = str(slot), "archival neutral (story's world)"
        for _, kept in bank:
            kept.unlink(missing_ok=True)

        # abstract may still generate, gated and labelled, before text-only
        if photo is None and kind == "abstract":
            gen = _generated_frame(frame, slot)
            if gen is not None:
                photo, tier = gen, "generated (labelled)"

        # the true last resort — rendered with the designed watermark
        # treatment, never a bare beige frame
        if photo is None:
            tier = "text-only (designed, last resort)"
        elif tier in ("relevant photo", "verified portrait",
                      "general photo (last resort)",
                      "archival neutral (story's world)"):
            used.add(_photo_digest(photo))
        print(f"    frame {n}: {tier}")
        photos.append(photo)

    # typographic frames count as illustrated (owner decision): a frame
    # whose text carries a strong figure renders it huge in the photo zone
    text_only = [i for i, ph in enumerate(photos, 1)
                 if ph is None and not _frame_figure(
                     frames[i - 1].get("text", ""),
                     frames[i - 1].get("punch", ""),
                     frames[i - 1].get("heading", ""))]
    if len(text_only) > STORY_MAX_BLANK_FRAMES:
        # mostly-blank decks don't ship (owner's rule): the caller records
        # the skip and advances to the next story rather than losing the slot
        vision_gate_summary()
        print(f"  ! {len(text_only)} of {len(frames)} frames have no visual "
              f"(no photo, no logo) — skipping this story, not shipping it")
        if story_has_company:
            _LAST_SKIP = (f"logo unavailable, {len(text_only)}/{len(frames)} "
                          "frames would be blank")
        else:
            _LAST_SKIP = (f"no archival photos found, {len(text_only)}"
                          f"/{len(frames)} frames would be blank")
        return None
    if text_only:
        print(f"    text-only frames this deck: {text_only} — designed "
              "watermark treatment, within the blank budget")
    vision_gate_summary()
    register_photos(photos, "story")
    return photos


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # A story typed by hand is run as asked — the portrait check exists to
    # spend the research budget well, not to overrule a deliberate choice.
    misses = 0
    if STORY:
        story = resolve_story_input(STORY)
    else:
        story, misses = pick_story()

    if not story:
        print(f"  ! no story with a usable portrait after {STORY_ATTEMPTS} tries")
        notify(f"⚠️ {ksa_stamp()} — no story published: {misses} candidates in "
               "a row had no portrait. Check the image sources, or add "
               "stories that aren't about a person.")
        return

    # one quiet miss is routine; a run of them means something is wrong
    if misses >= PORTRAIT_ALERT_AFTER:
        notify(f"⚠️ {ksa_stamp()} — skipped {misses} stories in a row for want "
               f"of a portrait before settling on:\n{story}")

    # A skip discovered at the photo stage advances to the next eligible
    # story in the SAME run — the slot is never lost to one unillustrable
    # subject. The skip file doubles as the exclusion, exactly like the
    # portrait gate: mark_skipped writes it, the next pick avoids it.
    photos = None
    failed_this_run = []
    for attempt in range(3):
        print(f"1/3 researching: {story}")
        try:
            brief = research(story)
        except RuntimeError as exc:
            # a transient API failure is not the story's fault: it returns
            # to the pool untouched — not used, not skipped — and the run
            # moves to the next candidate instead of dying
            print(f"  ! research failed for this candidate: {exc}")
            failed_this_run.append(story)
            if STORY:
                raise SystemExit(f"manual story research failed: {exc}")
            story, misses = pick_story(exclude=failed_this_run)
            if not story:
                break
            continue
        # the stories.txt line rides along so the logo rung can check the
        # owner's declared aliases as subject identity
        brief["story"] = story
        print(f"    {brief['title']}")
        for n, f in enumerate(brief.get("frames", []), 1):
            print(f"    {n}. {f.get('heading', '')} — {f.get('text', '')[:60]}")
        warn_about_unintroduced_names(brief)
        warn_about_misplaced_hooks(brief)

        print("2/3 finding a picture for every frame...")
        photos = find_all_photos(brief)
        if photos is not None:
            break
        reason = _LAST_SKIP or "insufficient visuals"
        commit_and_push(
            mark_skipped(story, brief.get("title", story),
                         reason="no_logo_insufficient_visuals"),
            f"story skipped (visuals): {story[:40]}")
        notify(f"⚠️ {ksa_stamp()} — story skipped: {story}\n"
               f"{reason}. Flagged for review in stories_skipped.json.")
        if STORY:
            print("  ! manual story skipped for insufficient visuals — "
                  "not advancing (explicit input)")
            return
        story, misses = pick_story(exclude=failed_this_run)
        if not story:
            print("  ! no eligible story left this run — ending without "
                  "publishing rather than shipping a blank deck")
            break
    if photos is None:
        notify(f"⚠️ {ksa_stamp()} — no story published this run: every "
               "candidate failed research or could not be illustrated.")
        raise SystemExit("run produced nothing")
    stamp = ksa_stamp()
    frames = build_frames(brief, stamp, photos)
    print(f"    {len(frames)} frames written")

    if DRY_RUN:
        print(f"    DRY_RUN — nothing published. Frames in {OUT_DIR.resolve()}")
        notify_album(f"[DRY RUN] would have published: {brief['title']}\n"
                     f"{len(frames)} لقطات — تجربة، لم تُنشر",
                     frames, as_documents=True)
        return

    slug = re.sub(r"[^\w]+", "-", story, flags=re.UNICODE)[:40].strip("-")

    if not POST_ENABLED:
        print("3/3 hybrid mode — publishing the frames, not posting")
        # The caption lives only in the brief, and the brief is gone once this
        # run ends. publish_cards.py needs it to post these frames later
        # without researching the story again, so leave it beside them.
        urls = publish_many_via_github(frames)
        # The frame list goes in too, by final committed name. Two runs in one
        # KSA hour leave two sets under one stamp (content-hashed names, so
        # neither overwrites) and a glob would stitch a story out of both.
        # The sidecar is written by the run that owns it, after the names are
        # final, so the publisher can post exactly this set.
        from news_bot import _card_destination
        (Path(CARDS_DIR) / f"{stamp}-story.json").write_text(
            json.dumps({"title": brief.get("title", ""),
                        "caption": brief.get("caption", ""),
                        "story": story,
                        "frames": [_card_destination(f).name for f in frames]},
                       ensure_ascii=False, indent=1),
            encoding="utf-8")
        commit_and_push(Path(CARDS_DIR) / f"{stamp}-story.json",
                        f"story sidecar {stamp}")
        for u in urls:
            print(f"    {u}")
        commit_and_push(save_used(load_used(), story), f"story: {slug}")
        if not STORY:
            # count the pool the story ACTUALLY came from
            bump_mix(story_pool(story))
        notify_album(f"{recent_warning()}📖 {stamp} — {brief['title']}\n"
                     f"{len(frames)} لقطات — الملفات مرقّمة 01..N للرفع "
                     "بالترتيب",
                     frames, as_documents=True)
        return

    if not quota_ok():
        deliver_unposted(frames, brief["title"])
        return

    print("3/3 posting the story to Snapchat...")
    urls = []
    if POST_PROVIDER != "bundle":
        urls = (publish_many_via_github(frames) if MEDIA_MODE == "github"
                else [upload_media(f) for f in frames])

    response = post_story(brief.get("caption", story), urls, frames)
    print("   ", response)

    if post_ok(response):
        commit_and_push(save_used(load_used(), story), f"story: {slug}")
        if not STORY:
            # count the pool the story ACTUALLY came from
            bump_mix(story_pool(story))
        commit_and_push(quota_bump(), f"quota {stamp}")
        notify_album(f"✅ {stamp} — {brief['title']}", frames,
                     as_documents=True)
    else:
        notify(f"❌ {stamp} — story post failed\n{describe_failure(response)}")


if __name__ == "__main__":
    main()
