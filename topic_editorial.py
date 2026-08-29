"""Pure editorial helpers for the Saudi Snapchat topic bot."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

_CATEGORY_RE = re.compile(r"^#\s*═+\s*(.*?)\s*═+\s*$")
_STRONG_REASON_PREFIXES = (
    "طلبه متابع",
    "في أخبار الأمس:",
    "موسم:",
    "الدورة الشهرية:",
)
_AR_MONTHS = (
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
)

_FINANCE_CONTEXT_RE = re.compile(
    r"قرض|تمويل|قسط|فائدة|الفيدرالي|سايبور|سعر الفائدة|الريال|الدولار|ساما",
    re.IGNORECASE,
)
_FINANCE_OVERCLAIM_RES = (
    re.compile(
        r"(?:قسطك|قرضك|تمويلك).{0,45}(?:مرتبط|مربوط).{0,45}"
        r"(?:واشنطن|أمريكا|الولايات المتحدة|الفيدرالي)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:قرار|قرارات)\s+الفيدرالي.{0,35}(?:يوصلك|يصل\s*لك|يحدد\s+قسطك|يتحكم\s+بقسطك)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:واشنطن.{0,24}(?:مو|وليس|بدل)\s+الرياض|"
        r"الرياض.{0,24}(?:مو|وليس|بدل)\s+واشنطن)",
        re.IGNORECASE,
    ),
)
_FINANCE_POLICY_ONLY_RES = (
    re.compile(
        r"(?:المتغير|تمويلك\s+المتغير|التمويل\s+المتغير).{0,55}"
        r"(?:فقط|بس).{0,30}(?:غي[ّ]?ر|تغي[ّ]?ر).{0,25}(?:ساما|الريبو|إعادة الشراء)",
        re.IGNORECASE,
    ),
)
_INSTITUTION_RELATION_RES = (
    re.compile(
        r"(?:ساما|البنك\s+المركزي\s+السعودي).{0,20}"
        r"(?:لحق|تبع|يتبع|مشى\s+ورا|يمشي\s+ورا|على\s+خطى|حذا\s+حذو|نسخ|قل[ّ]?د)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:الفيدرالي|Federal\s+Reserve).{0,45}(?:وساما|و\s*ساما|والبنك\s+المركزي\s+السعودي).{0,20}"
        r"(?:لحق|تبع|يتبع|مشى\s+ورا|يمشي\s+ورا|على\s+خطى|حذا\s+حذو|نسخ|قل[ّ]?د)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:ساما|البنك\s+المركزي\s+السعودي).{0,30}(?:مثل|نفس|كما|على\s+غرار).{0,25}"
        r"(?:الفيدرالي|Federal\s+Reserve)",
        re.IGNORECASE,
    ),
    # Run #74 leak: "الفيدرالي ثابت وساما مثله" still implies that one
    # institution's stance is best described by comparison with the other.
    re.compile(
        r"(?:الفيدرالي|Federal\s+Reserve).{0,45}(?:وساما|و\s*ساما|والبنك\s+المركزي\s+السعودي)"
        r".{0,20}(?:مثله|نفسه|نفس\s+(?:القرار|الخطوة|الاتجاه)|بنفس\s+(?:الخطوة|الاتجاه))",
        re.IGNORECASE,
    ),
)
_FED_TEXT_RE = re.compile(r"الفيدرالي|Federal\s+Reserve", re.IGNORECASE)
_FED_SOURCE_RE = re.compile(r"Federal\s+Reserve|الاحتياطي\s+الفيدرالي|الفيدرالي\s+الأمريكي", re.IGNORECASE)
_SAMA_SOURCE_RE = re.compile(r"\bSAMA\b|ساما|البنك\s+المركزي\s+السعودي", re.IGNORECASE)

_INSTRUCTIONAL_RE = re.compile(
    r"(?:^|[\s،,:؛.!؟])"
    r"(?:راجع|تأكد|قارن|احسب|راقب|تابع|اسأل|تحقق|افحص|اختر|احتفظ|احفظ|"
    r"جر[ّ]?ب|ابدأ|انتبه|تجن[ّ]?ب|تجنب|"
    r"لا\s+(?:تفترض|تنس|تعتمد|تتجاهل))"
    r"(?=$|[\s،,:؛.!؟])",
    re.IGNORECASE | re.MULTILINE,
)
_ADVISORY_RE = re.compile(
    r"(?:ننصحك|نصيحتنا|خطوتك\s+(?:الآن|التالية)|وش\s+تسوي|ماذا\s+تفعل)",
    re.IGNORECASE,
)


def load_topics_with_categories(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []

    category = "عام"
    topics: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        heading = _CATEGORY_RE.match(line)
        if heading:
            category = heading.group(1).strip() or "عام"
            continue
        if line.startswith("#"):
            continue
        name, _, trigger_text = line.partition("|")
        name = name.strip()
        if not name:
            continue
        topics.append({
            "topic": name,
            "triggers": [item.strip().lower() for item in trigger_text.split(",") if item.strip()],
            "category": category,
        })
    return topics


def _has_strong_signal(row: dict[str, Any]) -> bool:
    return any(str(reason).startswith(_STRONG_REASON_PREFIXES) for reason in row.get("reasons", []))


def balanced_shortlist(scored: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    ordered = sorted(scored, key=lambda row: -row.get("score", 0))
    chosen: list[dict[str, Any]] = []
    chosen_ids: set[int] = set()

    for row in ordered:
        if _has_strong_signal(row):
            chosen.append(row)
            chosen_ids.add(id(row))
            if len(chosen) == limit:
                return chosen

    seen_categories: set[str] = set()
    for row in ordered:
        if id(row) in chosen_ids:
            continue
        category = str(row.get("category") or "عام")
        if category in seen_categories:
            continue
        chosen.append(row)
        chosen_ids.add(id(row))
        seen_categories.add(category)
        if len(chosen) == limit:
            return chosen

    for row in ordered:
        if id(row) in chosen_ids:
            continue
        chosen.append(row)
        if len(chosen) == limit:
            break
    return chosen


def load_performance(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def performance_adjustment(topic: str, category: str, performance: dict[str, Any]) -> int:
    categories = performance.get("categories", {})
    topics = performance.get("topics", {})
    category_score = categories.get(category, 0) if isinstance(categories, dict) else 0
    topic_score = topics.get(topic, 0) if isinstance(topics, dict) else 0
    try:
        raw = float(category_score) + float(topic_score)
    except (TypeError, ValueError):
        raw = 0
    return int(max(-15, min(15, round(raw))))


def _instructional_tone_errors(brief: dict[str, Any]) -> list[str]:
    """Keep Topic Brief in an editorial voice rather than advice/teaching mode."""
    text = "\n".join(
        str(brief.get(field, "") or "").strip()
        for field in ("title", "body", "takeaway", "caption")
    )
    if _INSTRUCTIONAL_RE.search(text) or _ADVISORY_RE.search(text):
        return [
            "topic brief sounds instructional or advisory; state the fact, context, or "
            "significance without telling the audience what to do"
        ]
    return []


def _finance_tone_errors(brief: dict[str, Any]) -> list[str]:
    text = "\n".join(
        str(brief.get(field, "") or "").strip()
        for field in ("title", "body", "takeaway", "caption")
    )
    if not _FINANCE_CONTEXT_RE.search(text):
        return []

    errors: list[str] = []
    if any(pattern.search(text) for pattern in _FINANCE_OVERCLAIM_RES):
        errors.append(
            "financial wording overstates an indirect financial relationship; "
            "explain the local mechanism and use conditional language"
        )
    if any(pattern.search(text) for pattern in _FINANCE_POLICY_ONLY_RES):
        errors.append(
            "policy rate is not the only driver of variable financing; explain the "
            "contract benchmark, bank margin, and repricing schedule"
        )
    if any(pattern.search(text) for pattern in _INSTITUTION_RELATION_RES):
        errors.append(
            "state each institution's decision separately; avoid following, imitation, "
            "or side-by-side comparison language"
        )

    sources = brief.get("sources")
    if _FED_TEXT_RE.search(text) and isinstance(sources, list):
        source_text = "\n".join(str(item) for item in sources)
        if not (_FED_SOURCE_RE.search(source_text) and _SAMA_SOURCE_RE.search(source_text)):
            errors.append(
                "Federal Reserve and SAMA primary sources are required for a Fed-to-Saudi finance explanation"
            )
    return errors


def validate_brief(brief: Any) -> list[str]:
    if not isinstance(brief, dict):
        return ["brief must be a JSON object"]

    errors: list[str] = []
    limits = {"title": 45, "body": 260, "takeaway": 110, "caption": 120}
    for field, max_chars in limits.items():
        value = brief.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} is required")
            continue
        if len(value.strip()) > max_chars:
            errors.append(f"{field} exceeds {max_chars} characters")
        if re.search(r"<[^>]+>|\[\d+\]", value):
            errors.append(f"{field} contains citation markup")

    sources = brief.get("sources")
    if not isinstance(sources, list) or not 2 <= len(sources) <= 4 or not all(
        isinstance(item, str) and item.strip() for item in sources
    ):
        errors.append("sources must contain 2 to 4 names")

    for field in ("image_queries", "image_queries_ar"):
        value = brief.get(field)
        if not isinstance(value, list) or len(value) != 3 or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            errors.append(f"{field} must contain exactly 3 non-empty items")

    prompt = brief.get("image_prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append("image_prompt is required")

    source_url = brief.get("source_url")
    if not isinstance(source_url, str) or not re.match(r"^https?://", source_url.strip()):
        errors.append("source_url must be an http(s) URL")

    errors.extend(_instructional_tone_errors(brief))
    errors.extend(_finance_tone_errors(brief))
    return errors


def _ksa_date_text(today: date) -> str:
    return f"{today.day} {_AR_MONTHS[today.month - 1]} {today.year}"


def enhance_prompt(base_prompt: str, today: date | None = None) -> str:
    today = today or date.today()
    prompt = base_prompt.replace(
        "- sources: أسماء المصادر (٢ إلى ٤). إن كان المصدر أجنبياً فاكتبه بالعربية.",
        "- sources: أسماء المصادر (٢ إلى ٤). أبقِ أسماء المصادر العالمية المعروفة "
        "بكتابتها الأصلية مثل Reuters وBloomberg وCNBC وBBC، واكتب أسماء الجهات "
        "السعودية والعربية بالعربية.",
    )
    prompt = prompt.replace(
        "قواعد اللهجة والمصطلح — اكتب بلسان سعودي رسمي:",
        "قواعد اللهجة والمصطلح — اكتب بعربية حديثة قريبة من كلام الناس في السعودية:",
    )
    prompt = prompt.replace(
        '- قل "المملكة" لا "السعودية" في كل مرة، و"المواطنين" و"المقيمين" حين يلزم.',
        '- استخدم "السعودية" أو "المملكة" بحسب ما يبدو طبيعياً في الجملة، ولا تكرر صيغة واحدة آلياً.',
    )
    prompt += (
        "\n\nسياق النشر الحالي:\n"
        f"- تاريخ اليوم في السعودية: {_ksa_date_text(today)}.\n"
        "- الجمهور: جمهور سعودي عربي على سناب شات؛ الأولوية لما يوقف التمرير لأنه "
        "يمس الحياة اليومية أو المال أو العمل أو التقنية أو السيارات أو الرياضة أو "
        "الترفيه في السعودية.\n"
        "- دور Topic Brief هو إبراز موضوع مهم أو زاوية تستحق الانتباه وشرح معناها باختصار. "
        "ليس دورك أن تعلّم المتابع أو تعطيه واجباً أو نصيحة أو خطوات ينفذها.\n"
        "- لا تستخدم صيغة الأمر أو الدعوة إلى إجراء: لا تقل «راجع»، «قارن»، «تابع»، «راقب»، "
        "«تأكد»، «احسب»، «اسأل» أو ما يشبهها. حوّلها إلى معلومة خبرية تصف ما يحدث ولماذا يهم.\n"
        "- حقل takeaway ليس نصيحة ولا call to action. اجعله جملة خبرية قصيرة تلخص الدلالة "
        "الأهم أو السياق الذي ينبغي أن يبقى في ذهن المتابع، من دون توجيهه لفعل شيء.\n"
        "- العنوان الجذاب يفتح فضولاً حقيقياً ولا يصنع صدمة لفظية. إذا كان العنوان "
        "يعطي انطباعاً يحتاج المتن إلى تصحيحه لاحقاً، فأعد كتابة العنوان.\n"
        "- لا تحوّل النص إلى لهجة ثقيلة. استخدم فصحى مبسطة بإيقاع سعودي طبيعي، ويمكن "
        "استخدام كلمة سعودية مألوفة حين تجعل الجملة أقرب ولا تضعف المصداقية.\n"
        "- عندما يكون الموضوع زمنياً (اليوم، هذا العام، الأسعار الحالية، أين وصل)، "
        "تحقق من أحدث مصدر موثوق متاح وفضّل المصدر الرسمي أو الأولي.\n"
        "- الصور جزء من التحرير وليست زينة. اجعل image_queries تصف الموضوع نفسه أو الجهة أو "
        "الحدث المحدد، ولا تستخدم شارعاً أو سوقاً أو أفق الرياض كبديل عام إلا إذا كان المكان "
        "هو موضوع البطاقة فعلاً. image_prompt يجب أن يطلب صورة تحريرية عالية الجودة، واقعية، "
        "نظيفة التكوين، مرتبطة مباشرة بالموضوع، بلا نصوص أو شعارات أو كولاج.\n"
        "\nقواعد خاصة بالمال والتمويل والاقتصاد:\n"
        "- فرّق بوضوح بين العلاقة المباشرة وغير المباشرة. إذا كان حدث خارجي يؤثر عبر "
        "سعر الفائدة أو سعر الصرف أو سياسة محلية، قل «يؤثر» أو «ينعكس» أو «قد يتأثر»، "
        "ولا تقدمه كأنه يحدد مال القارئ مباشرة.\n"
        "- ممنوع استخدام مفارقة جغرافية صادمة لتبسيط علاقة اقتصادية معقدة. مثال مرفوض: "
        "«قسطك مرتبط بقرار في واشنطن مو الرياض». هذه جملة مثيرة لكنها مضللة وغير مريحة.\n"
        "- بدلاً من ذلك، اجعل الفضول في سؤال واضح عن معنى التطور نفسه، مثل: «وش يعني ثبات "
        "الفائدة للتمويل المتغير؟» ثم اشرح الآلية بجمل قصيرة من دون توجيه القارئ.\n"
        "- إذا كان الأثر يختلف حسب المنتج أو العقد، لا تخاطب الجميع كأن النتيجة واحدة. "
        "صف الاختلاف نفسه: التمويل المتغير يتأثر وفق المؤشر المرجعي والهامش وموعد إعادة التسعير.\n"
        "- عند ذكر الفيدرالي والبنك المركزي السعودي في الموضوع نفسه، اعرض قرار كل جهة على حدة "
        "بصياغة محايدة، ثم اشرح العلاقة النقدية في جملة منفصلة. لا تصغ العنوان أو المتن "
        "كحركة مشتركة أو مقارنة بين المؤسستين.\n"
        "- اجعل العنوان عن أهمية المعلومة أو معناها للمتابع، لا عن العلاقة بين المؤسسات.\n"
        "- في التمويل المتغير، لا تجعل سعر الريبو عند ساما هو المفتاح الوحيد. المؤشر قد يكون "
        "سايبور أو مؤشراً آخر، ثم يضاف هامش البنك، ويتغير السعر بحسب موعد إعادة التسعير "
        "المحدد في العقد. تحركات السياسة النقدية تؤثر في البيئة التمويلية، لكنها ليست وحدها "
        "ما يحدد كل قسط متغير.\n"
        "- في موضوع الفيدرالي والسعودية: اشرح أن ارتباط الريال بالدولار يجعل تحركات الفائدة "
        "الأمريكية مهمة للبيئة النقدية في السعودية، لكن تكلفة التمويل الفعلية تعتمد على "
        "المؤشر المرجعي في العقد ونوع المنتج وهامش البنك وموعد إعادة التسعير. لا تقل إن "
        "الفيدرالي «يحدد قسطك» أو إن قراره «يوصلك خلال أيام»، ولا تقل إن التمويل المتغير "
        "يتحرك فقط عندما يتغير سعر الريبو.\n"
        "- إذا ذكرت قراراً حديثاً للفيدرالي وتأثيره في السعودية، استخدم المصدرين الأوليين: "
        "Federal Reserve للقرار الأمريكي والبنك المركزي السعودي (ساما) للفائدة أو البيانات "
        "المحلية. يمكن إضافة مصدر صحفي للتفسير، لكن لا تستبدل المصدرين الأوليين به.\n"
        "- عند الحديث عن تمويل ثابت قائم، قل إن القسط أو السعر التعاقدي لا يعاد تسعيره عادةً "
        "بسبب قرار جديد؛ أما تمويل جديد أو إعادة تمويل فقد تتغير تكلفته مع ظروف السوق.\n"
        "- ركّز على ما الذي تغيّر، من الذي قد يتأثر، ولماذا تستحق المعلومة الانتباه الآن. "
        "الجاذبية تأتي من أهمية الموضوع والمعلومة الدقيقة، لا من النصيحة أو المبالغة.\n"
    )
    return prompt
