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
        fetch_generated_photo, IMAGE_SOURCE,
        photo_shows, vision_gate_summary,
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
ALLOW_STORY_GENERATION = os.getenv("ALLOW_STORY_GENERATION", "0").strip() \
    not in ("", "0", "false", "False")
# rather than lose a researched story, let a frame borrow another frame's photo
STORY_ALLOW_REPEAT = os.getenv("STORY_ALLOW_REPEAT", "1").strip() \
    not in ("0", "false", "False")
COOLDOWN_DAYS = int(os.getenv("STORY_COOLDOWN_DAYS", "").strip() or "60")

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

لكل لقطة:
- heading: سطر قصير جداً (حتى ٣٠ حرفاً) — يظهر كبيراً
- text: من جملتين إلى أربع جمل (١٢٠ إلى ٢٨٠ حرفاً).
  خذ راحتك: القصة المضغوطة تفقد معناها. اشرح السبب والنتيجة،
  لا العناوين فقط. لكن بلا حشو — كل جملة تضيف شيئاً جديداً.
- punch: اتركها فارغة "" في أغلب اللقطات.
  لا تملأها إلا إذا كان في اللقطة لحظة واحدة تستحق أن تقف وحدها: اقتباس قيل
  فعلاً، أو حكم، أو انقلاب في المسار. تُعرض بالأحمر وحدها تحت النص، ولذلك
  تُقرأ كأنها ذروة اللقطة — فإن وضعت فيها كلاماً عادياً بدت البطاقة كأنها
  تصيح بلا سبب.
  جملة واحدة قصيرة (حتى ٧٠ حرفاً). ولا تكرر ما في text بصياغة أخرى:
  هي جملة جديدة، لا خلاصة.
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

- image_keywords: من كلمتين إلى أربع كلمات إنجليزية بسيطة للبحث عن صورة
  حقيقية. أسماء علم فقط: اسم الشخص أو الشركة أو المنتج أو المكان.
  ✓ ["Steve Jobs", "Macintosh 128K", "Apple Park"]
  ✗ ["a garage in California in 1976"]   ✗ ["office building", "modern desk"]

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
    head = re.sub(r"^\s*قصة\s+", "", str(story or "").strip())
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


def load_stories():
    try:
        lines = STORIES_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print(f"  ! {STORIES_FILE} not found")
        return []
    return [ln.strip() for ln in lines
            if ln.strip() and not ln.strip().startswith("#")]


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


def choose_story(exclude=()):
    stories = load_stories()
    if not stories:
        return ""
    used = {e["story"] for e in load_used()}
    used |= {e["story"] for e in load_skipped()}
    used |= set(exclude)
    fresh = [s for s in stories if s not in used]
    if not fresh:
        print("    every story used recently — starting the cycle again")
        fresh = stories
    # Hash the date rather than use the ordinal directly. The ordinal advances
    # by one a day, so consecutive days took consecutive entries — and
    # stories.txt is grouped by section, so a daily story walked straight down
    # one theme: seven businessmen in a row, then seven cities. Invisible at
    # two a week, dominant at one a day. Still deterministic per day, so a
    # retry inside one run picks the same story.
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


def mark_skipped(story, name):
    """Remember the miss, so tomorrow's run doesn't spend the same searches
    rediscovering that this person has no picture."""
    SKIPPED_FILE.parent.mkdir(parents=True, exist_ok=True)
    entries = load_skipped() + [{"story": story, "name": name,
                                 "at": datetime.now().isoformat()}]
    SKIPPED_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    return SKIPPED_FILE


def find_portrait(name, out_path):
    """A real photograph of this person, or None.

    Commons goes first and matters most: its second lookup is the lead image
    of the person's own article, which is where a portrait actually lives.
    """
    photo, _ = fetch_local_photo([], [name], out_path)
    if photo:
        return photo
    photo, _ = fetch_commons_portrait(name, out_path)
    return photo


def pick_story():
    """Choose a story we can actually illustrate.

    Person-led stories are checked for a portrait before anything is spent on
    research. Stories about a company, a city or a product are returned as-is
    — there is no single face to look for, and their pictures are found the
    ordinary way once the frames exist.

    Returns (story, misses).
    """
    tried, misses = [], 0
    for _ in range(STORY_ATTEMPTS):
        story = choose_story(exclude=tried)
        if not story:
            break
        name = person_name(story)
        if not name:
            return story, misses
        print(f"    checking for a portrait of {name}...")
        if find_portrait(name, OUT_DIR / "portrait.jpg"):
            return story, misses
        print(f"  · no portrait for {name} — trying another story")
        commit_and_push(mark_skipped(story, name), f"no portrait: {name}")
        tried.append(story)
        misses += 1
    return "", misses


def research(story):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    messages = [{"role": "user", "content": f"القصة: {story}"}]
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
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"Claude API {exc.code}: {exc.read().decode()[:400]}")

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
                messages = [{"role": "user", "content": f"القصة: {story}"}]
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
    shaped, k = ar(counter)
    draw.text((margin, 216), shaped, font=load_font(28), fill=MUTED,
              anchor="la", **k)

    y = 420
    if photo:
        try:
            pic = Image.open(photo).convert("RGB")
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
    if not photo:
        y = (H - len(lines) * int(size * 1.25)) // 2 - 140
    for line in lines:
        mid(y, line, f_big, TEXT)
        y += int(size * 1.25)

    bottom = (H - 260 if footer else H - 180)

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
        for line in lines:
            mid(y, line, f_sub, sub_colour or BODY)
            y += line_gap

    if punch_lines:
        y += PUNCH_GAP
        for line in punch_lines:
            mid(y, line, f_punch, ACCENT)
            y += punch_gap

    if footer:
        f_foot = load_font(26)
        text = footer
        while text and draw.textlength(ar(text)[0], font=f_foot, **kw) > max_w:
            if "، " in text:
                text = text.rsplit("، ", 1)[0]      # drop the last source
            else:
                text = text[:-4]
        draw.line([(centre - 130, H - 206), (centre + 130, H - 206)],
                  fill=RULE, width=2)
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
        paths.append(render_frame(
            OUT_DIR / f"{stamp}-story-{n}.png", BRAND, f"{n} / {total}",
            heading, 60, sub=frame.get("text", ""),
            sub_colour=ACCENT if (last and not punch) else None,
            photo=photos[n - 1], punch=punch,
            footer=(f"المصدر: {sources}" if sources else None) if last else None))

    return [str(p) for p in paths]


def _photo_digest(path):
    """Perceptual hash, so the same picture found twice reads as the same.

    Byte-hashing missed a real repeat: frames 1 and 6 of one story fetched
    the same image through different downloads — a re-encode, different
    bytes — and md5 called them distinct. A 16x16 average hash sees the
    picture, not the file.
    """
    try:
        from PIL import Image
        img = Image.open(path).convert("L").resize((16, 16))
        px = list(img.getdata())
        mean = sum(px) / len(px)
        return "".join("1" if v > mean else "0" for v in px)
    except Exception:
        return None


def find_photo(spec, out_path, seen=(), context="", allow_neutral=True):
    """One photo for one frame, searched by subject.

    Any real photograph about the story serves — the person, the product, the
    building, the logo. A single keyword match is enough here, because we are
    searching for a subject rather than matching a described scene.

    Anything already used elsewhere in this story is refused and the search
    carries on: the same picture on two frames of one series reads as a
    mistake, and the reader notices it before they notice the text.
    """
    # A frame whose subject has no archive photo at all used to die here and
    # take the whole story with it — the first gated run rejected everything
    # for every frame. "neutral" (a real photograph that misleads no one but
    # proves nothing) is banked and used only if no "yes" ever arrives.
    neutral = Path(str(out_path) + ".neutral")
    neutral.unlink(missing_ok=True)

    def take(result):
        photo = result[0] if isinstance(result, tuple) else result
        if not photo:
            return None
        if _photo_digest(photo) in seen:
            print("      (that picture is already on an earlier frame "
                  "— looking further)")
            return None
        if not context:
            return photo
        verdict = photo_shows(photo, context)
        if verdict == "yes":
            return photo
        # A widened search must not bank neutrals: story-level fallback plus
        # a generic Arabic single («صحراء») pulled global results, the gate
        # called them harmless, and a Tunisian tourism photo shipped on a
        # Saudi story. Only a frame's OWN keywords may settle for neutral —
        # widening either finds the real thing or falls through to the loud
        # repeat of a correct photo.
        if allow_neutral and verdict == "neutral" and not neutral.exists():
            import shutil as _sh
            _sh.copyfile(photo, neutral)      # later fetches overwrite out_path
        return None

    def settle(photo):
        """A yes wins; otherwise the banked neutral carries the frame."""
        if photo is None and neutral.exists():
            import shutil as _sh
            _sh.copyfile(neutral, out_path)
            print("      (no photo shows this beat exactly — using a neutral "
                  "real photograph instead)")
            photo = str(out_path)
        neutral.unlink(missing_ok=True)
        return photo

    keywords = [k for k in (spec.get("image_keywords") or []) if k]
    if not keywords:
        keywords = spec.get("image_queries") or []
    keywords_ar = [k for k in (spec.get("image_keywords_ar") or []) if k]

    photo = take(fetch_local_photo([], keywords, out_path))

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
                                         min_hits=1, subject_mode=True))
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
                                           min_hits=1, subject_mode=True))

    if photo is None and ALLOW_STORY_GENERATION:
        # Nothing in the archive. Generating a building or an office produces
        # filler with invented signage, so ask for something plain instead.
        subject = keywords[0] if keywords else spec.get("heading", "")
        prompt = (f"A plain, unbranded photograph relating to {subject}. "
                  "No buildings with signs, no offices, no logos, no text.")
        photo = take(fetch_generated_photo(prompt, out_path))
    return settle(photo)


LOGOS_DIR = Path(os.getenv("LOGOS_DIR", "images/logos"))


def _curated_logo(frame_no, total, brief, frame):
    """An era-matched curated logo for this frame, or None.

    Deliberate editorial fallback, not photography: rule 3 rejects logo cards
    that ARRIVE FROM ARCHIVE SEARCH (filler on a news card), and that pixel
    check is untouched — files never enter through it here. Provenance is the
    carve-out: only files sitting in images/logos/, placed there by the owner
    (renaming a reviewed candidate into the folder is the approval step), are
    eligible. The vision gate is skipped for the same reason — it would say
    "not a real photograph", which is true and beside the point.
    """
    if frame_no == 2:
        return None            # the protagonist frame shows a face, never a logo
    try:
        files = sorted(LOGOS_DIR.glob("*.png"))
    except OSError:
        return None
    if not files:
        return None

    # what this story talks about, in both scripts
    hay = " ".join(filter(None, [
        str(brief.get("story", "")),
        str(brief.get("title", "")),
        " ".join(brief.get("image_keywords", []) or []),
        " ".join(brief.get("image_queries_ar", []) or []),
        " ".join(frame.get("image_keywords", []) or []),
        " ".join(frame.get("image_keywords_ar", []) or []),
    ])).lower()

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
        names = [slug] + list(aliases.get(slug, []))
        if not any(len(nm) >= 3 and nm.lower() in hay for nm in names):
            continue
        key = float("inf") if era == "current" else             int(era) if era.isdigit() and len(era) == 4 else None
        if key is None:
            continue
        candidates.setdefault(slug, []).append((key, f))
    if not candidates:
        return None

    eras = sorted(next(iter(candidates.values())))
    # era by frame position only: opening takes the oldest, the closing frame
    # takes -current (or the newest on file), middle frames interpolate
    if len(eras) == 1:
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
    print(f"    frame {frame_no}: using curated logo {path} (era match: {tag})")
    return str(dest)

def find_all_photos(brief):
    """A picture for every frame, trying progressively wider searches.

    1. the frame's own keywords, in English then in Arabic
    2. the story's subject (from the title and the first frame)
    3. repeat a photo already used on another frame

    No two frames get the same picture unless step 3 is reached, and step 3
    is a visible flaw rather than a neutral fallback — a six-frame story with
    the same photograph twice looks like nobody checked it.

    Only if all three fail for some frame is the story abandoned — a story
    costs a research call, so it is worth widening the net before giving up.
    """
    frames = brief.get("frames", [])[:STORY_FRAMES]
    # Subject terms, for widening a frame that found nothing on its own.
    # Frame 2 names the protagonist and frame 1 the setting — a person's name
    # is the more findable of the two, so it goes first. (Before the structure
    # was rewritten the protagonist was in frame 1, and this only read frame 1.)
    fallback = list(brief.get("image_keywords", []))
    for frame in frames[1:2] + frames[0:1]:
        fallback += [k for k in (frame.get("image_keywords") or []) if k][:2]
    fallback = [k for k in dict.fromkeys(fallback) if k][:3]
    # story-level Arabic keywords: the same for every frame, so they are only
    # a backstop for a frame the model gave none of its own
    fallback_ar = [k for k in (brief.get("image_queries_ar") or []) if k][:3]

    photos, missing = [], []
    used = set()                      # digests of pictures already in the story
    for n, frame in enumerate(frames, 1):
        spec = dict(frame)
        # An explicit [] is an answer, not a gap: the prompt asks for it when
        # a beat is purely foreign, and forcing the story's Arabic keywords
        # onto such a frame is how you attach a Saudi photo to a beat about
        # Fairchild. Only a missing field falls back. The story-level terms
        # still get their turn at the widening step below.
        own_ar = frame.get("image_keywords_ar")
        spec["image_keywords_ar"] = (fallback_ar if own_ar is None
                                     else [k for k in own_ar if k])
        keywords = [k for k in (spec.get("image_keywords") or []) if k]
        line = ", ".join(keywords[:4]) or "(no keywords)"
        if spec["image_keywords_ar"]:
            line += f"  |  {', '.join(spec['image_keywords_ar'][:3])}"
        print(f"    frame {n}: {line}")

        context = f"{frame.get('heading', '')}\n{frame.get('text', '')}".strip()
        photo = find_photo(spec, OUT_DIR / f"story-frame-{n}.jpg", used, context)

        if photo is None and fallback:
            print(f"      widening to the story subject: {', '.join(fallback)}")
            photo = find_photo({"image_keywords": fallback,
                                "image_keywords_ar": fallback_ar},
                               OUT_DIR / f"story-frame-{n}.jpg", used, context,
                               allow_neutral=False)

        # curated logo before the repeat fallback; a single logo may serve
        # more than one frame (the spec allows it), so logo frames stay out
        # of the `used` digests that the no-repeat rule checks
        from_logo = False
        if photo is None:
            photo = _curated_logo(n, len(frames), brief, frame)
            from_logo = photo is not None

        if photo is None:
            missing.append(n)
        elif not from_logo:
            used.add(_photo_digest(photo))
        photos.append(photo)

    # Last resort. Every picture here is already on another frame, so this is
    # a repeat however it is spread — spread it anyway, so one photograph
    # doesn't end up carrying three frames, and say so loudly.
    found = [p for p in photos if p]
    if missing and found and STORY_ALLOW_REPEAT:
        import shutil as _shutil
        owner = {p: i + 1 for i, p in enumerate(photos) if p}
        uses = {p: 1 for p in found}          # each already appears once
        for n in missing:
            source = min(found, key=lambda p: uses[p])
            uses[source] += 1
            target = OUT_DIR / f"story-frame-{n}.jpg"
            _shutil.copyfile(source, target)
            photos[n - 1] = str(target)
            print(f"  ! frame {n} has no photo of its own — repeating the one "
                  f"from frame {owner[source]}")
        print(f"  ! {len(missing)} of {len(frames)} frames show a repeated "
              f"picture. Add keywords for those beats in stories.txt, or set "
              f"STORY_ALLOW_REPEAT=0 to skip the story instead.")
        missing = []

    if missing:
        vision_gate_summary()
        print(f"  ! frames {missing} found no picture at all")
        return None
    vision_gate_summary()
    return photos


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # A story typed by hand is run as asked — the portrait check exists to
    # spend the research budget well, not to overrule a deliberate choice.
    misses = 0
    if STORY:
        story = STORY
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

    print(f"1/3 researching: {story}")
    brief = research(story)
    print(f"    {brief['title']}")
    for n, f in enumerate(brief.get("frames", []), 1):
        print(f"    {n}. {f.get('heading', '')} — {f.get('text', '')[:60]}")
    warn_about_unintroduced_names(brief)

    print("2/3 finding a picture for every frame...")
    photos = find_all_photos(brief)
    if photos is None:
        notify(f"⚠️ {ksa_stamp()} — story skipped: no picture found\n"
               f"{story}")
        return
    stamp = ksa_stamp()
    frames = build_frames(brief, stamp, photos)
    print(f"    {len(frames)} frames written")

    if DRY_RUN:
        print(f"    DRY_RUN — nothing published. Frames in {OUT_DIR.resolve()}")
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
        notify_album(f"📖 {stamp} — {brief['title']}\n{len(frames)} لقطات",
                     frames)
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
        commit_and_push(quota_bump(), f"quota {stamp}")
        notify_album(f"✅ {stamp} — {brief['title']}", frames)
    else:
        notify(f"❌ {stamp} — story post failed\n{describe_failure(response)}")


if __name__ == "__main__":
    main()
