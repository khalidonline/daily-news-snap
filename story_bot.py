Warning: truncated output (original token count: 32284)
Total output lines: 2443

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
STORY_MODEL = _clean_model_id(os.getenv("STORY_MODEL"), "claude-sonnet-5")
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
PORTRAIT_ALERT_AFTER = int(os.getenv("PORTRAIT_ALERT_AFTER", "").strip(…12284 tokens truncated…RANKED candidates through the gate.
    # One best-scored offer used to be the library's whole say: the
    # coffee deck's dallah (top score, wrong angle) eclipsed the harvest
    # photo the farming frames were asking for — six gate rejections,
    # six blank frames, a skipped story with the right seed on disk.
    photo, tried_local = None, list(spec.get("lib_exclude") or [])
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


def company_frame_spec(subject_spec, frame_spec):
    """Keep company identity while preferring the frame's visual beat."""
    result = dict(frame_spec or {})
    for key in ("image_keywords", "image_keywords_ar"):
        own = [value for value in result.get(key, []) if value]
        subject = [value for value in (subject_spec or {}).get(key, []) if value]
        result[key] = list(dict.fromkeys(own + subject))
    return result


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
    # A PORTRAIT-tagged library file serves PERSON frames only — the
    # runtime face of image_precheck's slot/alias typing. The Bogle
    # world-frame took the story's only portrait through the general
    # rung, and the protagonist frame then met its own face as a
    # forbidden repeat: one portrait, spent on the wrong frame.
    person_names_all = {n.casefold() for n in
                        (_STORY_PERSONS.get(subject_line.strip()) or [])}
    pn = person_name(subject_line)
    if pn:
        person_names_all.add(pn.casefold())
    portrait_files = []
    if person_names_all:
        from news_bot import load_local_images
        for entry_img in load_local_images():
            tags = {t.casefold() for t in entry_img.get("tags", [])}
            if tags & person_names_all:
                portrait_files.append(entry_img["path"].name)
        if portrait_files:
            print(f"    portrait-class library files reserved for person "
                  f"frames: {portrait_files}")
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
                # The approved local pool is already story-scoped. Keep the
                # declared subject in every query, but prefer the visual beat
                # requested by this frame so distinct assets land on the
                # correct part of the timeline.
                spec = company_frame_spec(subject_spec, spec)
                context = f"القصة عن {subject_name}.\n{context}"
            # Historical stories BANK neutrals: a period photo of the
            # story's world that doesn't show this beat's exact subject is
            # precisely the right archival fallback for a 1602 frame — the
            # bank was removed because COMPANY decks abused it (sponsor
            # stadiums), so it returns kind-aware: no-company stories only.
            if photo is None:
                if portrait_files:
                    spec = dict(spec, lib_exclude=portrait_files)
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
        os.environ["STORY_USAGE_CONTEXT"] = story
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
