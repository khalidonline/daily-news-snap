# قالب المقارنات

المرجع المعتمد هو reference.png، النسخة الأخيرة من «وش اكثر مشروب يصحصحك ؟».
بطاقة معلومات ثابتة بمقاس 1080×1920. لكل عنصر اسم وأيقونة وقيمة بالأرقام الإنجليزية وشريط أفقي. توضح الوحدة وأساس المقارنة فوق الصفوف، وتشترك الأشرطة بمقياس واحد من الصفر. يظهر نطاق القيم بامتداد أفتح. تستخدم البطاقة هوية ملخص تنفيذي وعبارة المشاركة من المرجع.

لإنشاء بطاقة جديدة استخدم publishing_v2.comparison_template.render مع عنوان ووحدة وقائمة صفوف وأيقوناتها. في design-review اختر template بقيمة comparison وضع بيانات الرسم في comparison. تمر الصورة بمسار بطاقات المعلومات للقصة والحفظ.

## Closed approved variants (local implementation proposal)

`pictogram-count-v1` and `annotated-range-v1` are closed reference variants for
Sugar-Comparison.png and Mobile-Data-Comparison.png respectively. They are NOT
permission to accept arbitrary new charts or to alter the approved exports.
`publishing_v2.comparison_variants.SPECS` records the exact titles, subtitle,
unit/common basis, all rows, counts or interval endpoints, usage annotations,
footer note, scale/pictogram semantics and reference geometry. References are
hard-pinned by SHA-256 and all pixels are compared. At the shared design gate,
raw export bytes must also match, even if a re-encoded image looks identical.

For these variants, both each manifest media entry and its design-review card
must declare `template: comparison` and the identical complete `comparison`
specification. Existing current-settings, source/media seals, mobile review,
destination, owner authorization, account/quota and duplicate guards remain.
A reference comparison does not grant publication authorization or supply a
passed human review. Real destination overlay review is still required.

The old caffeine reference/rendering route is unchanged. This addition supplies
validation for these two immutable reviewed designs, not a generalized renderer.
A new unseen design or changed data/layout must not reuse these identifiers.
No publishing request, manifest approval, schedule change or API call is part
of this patch. Integration/push approval and normal package preparation plus
receipt reconciliation remain outstanding.
