# ذاكرة ملخص تنفيذي التحريرية

آخر تحديث: ٢٧ سبتمبر ٢٠٢٦ — نسخة القواعد `2026-09-27.1`.

المرجع التشغيلي الموحد: `publishing_v2/autopilot/owner_memory.py`.
سجل `Snapchat-Continuous-Improvement.md` يبقى أرشيف المراجعات التفصيلية؛ ليس
ملف تعليمات يقرأه كل نموذج تلقائيًا، ولا تم نقل الأرشيف كاملًا لكل طلب مدفوع.

## الموجود وكيف يستخدم

| المحتوى | وصوله للتشغيل |
|---|---|
| اللهجة السعودية والأسئلة الهادئة وعدم ضغط المتابع | تعليمات مشتركة، ثم قواعد موجزة تصل للكاتب والمراجعين |
| معلومة مفيدة تعرّف بالموضوع وقصة مترابطة تستاهل المشاركة | قواعد التحرير والأمثلة المعتمدة المستوردة من المرجع الموحد |
| أمثلة الأسلوب والملاحظات عن كثافة النص وتسلسل القصة والأسماء | حزم مستقلة داخل المرجع نفسه؛ الأمثلة ليست مصادر حقائق |
| مطابقة الصورة للمرحلة التاريخية ووجود صورة لكل بطاقة | قواعد مشتركة مع بقاء اختبارات الصور المستقلة |
| الترقيم العربي للقصة والهوية وبطاقة المصادر الداخلية | قواعد حالية مشتركة؛ أرقام المتن تحتفظ بضابط العرض الموجود |
| رفض زوايا أو باقات محددة | سجلات نطاقها باقة، تستخدم في فلترة المرشحين ومراجعة الباقة |
| اختيار مجاني ومرشح مدفوع واحد وحدود الصرف | قاعدة حالية تصل للنماذج، والمنع الفعلي في الكود ودفتر التكلفة |

لكل سجل معرف ونطاق وحالة ومصدر وطريقة استخدام. التعليمات المرحّلة من الكود
معلّمة بهذا المصدر؛ لا ننسبها تلقائيًا إلى رسالة أصلية لم نراجعها.
يسجل إيصال كل طلب جديد `owner_memory_version` حتى نعرف أي نسخة استُخدمت.
تغيير ملف الذاكرة يدخل في بصمة محرك الإنتاج ويبطل الاعتماد الآلي الأقدم كالمعتاد.

## تعليمات استُبدلت

- السماح بتجربة مرشح مدفوع آخر بعد رفض الأول: استبدلته قاعدة مرشح واحد، مع
  إصلاح البطاقات المتأثرة داخل سقف الباقة أو حفظ سبب التوقف.
- فرض افتتاح المعلومة بنتيجة الخبر الحالي: استبدلته قاعدة أن الطاري شرط
  للاختيار، وذكره في النص اختياري.
- إلزام كل بطاقة بتشويق أو سؤال: الصياغة الحالية تجعل الجسر أو السؤال
  اختياريًا، والنهاية الواضحة مقبولة.

السجلات القديمة محفوظة للتتبع ولا تُرسل كتعليمات فعالة. ملاحظة تخص باقة لا
تصير حظرًا دائمًا للموضوع كله؛ أي عودة تحتاج زاوية وطاري موثقين ومختلفين.

## حدود التوحيد

هذا توحيد للتعليمات الموجودة في الكود وتسوية التعارضات التي جرى التحقق منها،
وليس إثباتًا أن كل رسالة تاريخية للمستخدم استُوردت. سجل المراجعات لا يتزامن
مع الكود تلقائيًا. أي ملاحظة جديدة تحتاج تصنيفًا، وربطها بالقاعدة التي تعدّلها،
وتحديث النسخة واختبار وصولها للدور المناسب. لا يُنشأ نظام ذاكرة موازٍ.

الاختبارات تستخدم طلبات وهمية بلا اتصال مدفوع لإثبات وصول القواعد للكاتب
ومراجع النص والمراجع النهائي، وتسجيل النسخة، وعدم تسرب تعليمات الأرشيف.

## تحديث خالد — ٦ أكتوبر ٢٠٢٦: جودة اختيار الطواري

- ابدأ بمسح أهم عناوين أمس واليوم من مصادر سعودية وعربية وعالمية، ثم اختر بحسب أهمية الحدث وقربه من الجمهور السعودي؛ سهولة البحث وتوفر الصور لا ترفعان خبرًا ثانويًا فوق خبر رئيسي.
- قبل عرض المرشح: احسم تاريخ الحدث، والمعلومة المفيدة، والمنعطف والنتيجة الموثقين. المحتوى يجب أن يضيف معنى للخبر، لا مجموعة حقائق عامة.
- نفّذ جولة مقارنة وتحسين ثانية قبل إرسال القائمة، دون انتظار رفض خالد. عند ضعف البدائل قلّل العدد.
- المثال التعليمي: خبر اليمن وباب المندب أقوى كخبر رئيسي؛ ذكرى إنستغرام مناسبة ثانية مع تحول الفكرة والتركيز على الصور. الأمثلة ليست دعوة لتكرار الباقات.
- الطاري يظهر في البداية؛ بطاقة أو بطاقتان بنقاط، عنوان بسطر واحد وخط واضح.
- طُبّقت هذه التعليمات في طلب مهمة «طواري ملخص تنفيذي للاختيار» يوم ٦ أكتوبر؛ لا تغيير لموعدها أو موافقات النشر أو سقف ٣ دولارات.

## 2026-10-06 — compact readability enforcement

- New manual API deliveries must pass the image-bound `readability.json` check
  in `publishing_v2.bundle_api`; see `docs/compact-readability.md` for the exact
  report contract and its limits. Max two cards, three bullets per card, body
  48 px and CTA 38 px minimum at 1080×1920; headline one measured line.
- Keep a real mobile visual review. Metadata cannot prove how pixels were drawn.
- Preserve prior operation IDs for reconciliation. A new readability rule is
  never a reason to recreate an uncertain Snapchat post or regenerate paid work.
- Next three packages: count requested typography revisions after first preview;
  target zero. Compare share rate after 24 hours only when verified views and
  shares exist, at equal observation age; do not substitute ad benchmarks.

## 2026-10-06 20:07 Riyadh — Khalid rejected both energy drafts

Owner feedback (binding): the oil card had no compelling discovery; the Google
card was ambiguous, full of measurements for specialists, and its close-up
server photo was very weak and unexpressive. Both revision-1 designs are rejected,
not approved for publication or archiving.

Apply to future packages:
- A correct news summary is not enough. Name the one concrete discovery worth
  sharing before design. Infrastructure length/date/capacity alone do not pass.
- Explain cause and result with a familiar everyday example. Technical units
  need a useful everyday interpretation; omit numbers that require specialist
  knowledge or distract from the idea. Fewer words must not mean vaguer meaning.
- A photo must explain the main idea at phone size. Relevance to the industry
  alone is insufficient. Reject tight equipment shots whose meaning a general
  viewer cannot recognize. Prefer a verified wide scene showing scale, people,
  use or the actual consequence, with a precise caption.
- Pixel-size tests only establish typography. Before presenting a draft, answer:
  what will a general Saudi viewer discover, understand, and see in five seconds?
  A reviewer must flag a weak hook even when all technical checks pass.
- Revision 2 of these two cards still requires Khalid's publication approval.

### 2026-10-06 20:17 — oil revision
Khalid judged remote operation an unimportant detail. Prefer a meaningful
founding/completion milestone or expansion with a result. Never repeat a bullet
as the closing: use a distinct supported payoff or a short general takeaway.
Oil revision 3 replaces its third bullet and closing. Google revision 3 clarifies the headline to name the nuclear-electricity contract and its 20-year duration, as requested by Khalid; the rest of its card is unchanged.
