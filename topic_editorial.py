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
    # Run #71 pattern: a personal Saudi financial obligation is presented as
    # literally linked to a foreign city/policy maker rather than indirectly
    # influenced through monetary policy and local pricing.
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


def load_topics_with_categories(path: Path) -> list[dict[str, Any]]:
    """Parse topics.txt while retaining each major editorial category."""
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
            "triggers": [
                item.strip().lower()
                for item in trigger_text.split(",")
                if item.strip()
            ],
            "category": category,
        })
    return topics


def _has_strong_signal(row: dict[str, Any]) -> bool:
    return any(
        str(reason).startswith(_STRONG_REASON_PREFIXES)
        for reason in row.get("reasons", [])
    )


def balanced_shortlist(scored: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    """Keep strong live signals, then diversify evergreen candidates by category."""
    if limit <= 0:
        return []

    ordered = sorted(scored, key=lambda row: -row.get("score", 0))
    chosen: list[dict[str, Any]] = []
    chosen_ids: set[int] = set()

    # Current follower/news/season signals are allowed to cluster: relevance first.
    for row in ordered:
        if _has_strong_signal(row):
            chosen.append(row)
            chosen_ids.add(id(row))
            if len(chosen) == limit:
                return chosen

    # For evergreen slots, take one from each category before repeating a category.
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

    # If the catalog has fewer categories than slots, fill by score.
    for row in ordered:
        if id(row) in chosen_ids:
            continue
        chosen.append(row)
        if len(chosen) == limit:
            break
    return chosen


def load_performance(path: Path) -> dict[str, Any]:
    """Load optional audience-performance weights; missing/invalid data is neutral."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def performance_adjustment(topic: str, category: str, performance: dict[str, Any]) -> int:
    """Return a bounded score boost/penalty from historical audience response."""
    categories = performance.get("categories", {})
    topics = performance.get("topics", {})
    category_score = categories.get(category, 0) if isinstance(categories, dict) else 0
    topic_score = topics.get(topic, 0) if isinstance(topics, dict) else 0
    try:
        raw = float(category_score) + float(topic_score)
    except (TypeError, ValueError):
        raw = 0
    return int(max(-15, min(15, round(raw))))


def _finance_tone_errors(brief: dict[str, Any]) -> list[str]:
    """Block finance hooks that turn indirect influence into a literal claim."""
    text = "\n".join(
        str(brief.get(field, "") or "").strip()
        for field in ("title", "body", "takeaway", "caption")
    )
    if not _FINANCE_CONTEXT_RE.search(text):
        return []
    if any(pattern.search(text) for pattern in _FINANCE_OVERCLAIM_RES):
        return [
            "financial wording overstates an indirect financial relationship; "
            "explain the local mechanism and use conditional language"
        ]
    return []


def validate_brief(brief: Any) -> list[str]:
    """Return publish-blocking editorial/shape errors for one Snapchat brief."""
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

    errors.extend(_finance_tone_errors(brief))
    return errors


def _ksa_date_text(today: date) -> str:
    return f"{today.day} {_AR_MONTHS[today.month - 1]} {today.year}"


def enhance_prompt(base_prompt: str, today: date | None = None) -> str:
    """Resolve voice/source contradictions and inject current Saudi Snapchat context."""
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
        "- العنوان الجذاب يفتح فضولاً حقيقياً ولا يصنع صدمة لفظية. إذا كان العنوان "
        "يعطي انطباعاً يحتاج المتن إلى تصحيحه لاحقاً، فأعد كتابة العنوان.\n"
        "- لا تحوّل النص إلى لهجة ثقيلة. استخدم فصحى مبسطة بإيقاع سعودي طبيعي، ويمكن "
        "استخدام كلمة سعودية مألوفة حين تجعل الجملة أقرب ولا تضعف المصداقية.\n"
        "- عندما يكون الموضوع زمنياً (اليوم، هذا العام، الأسعار الحالية، أين وصل)، "
        "تحقق من أحدث مصدر موثوق متاح وفضّل المصدر الرسمي أو الأولي.\n"
        "\nقواعد خاصة بالمال والتمويل والاقتصاد:\n"
        "- فرّق بوضوح بين العلاقة المباشرة وغير المباشرة. إذا كان حدث خارجي يؤثر عبر "
        "سعر الفائدة أو سعر الصرف أو سياسة محلية، قل «يؤثر» أو «ينعكس» أو «قد يتأثر»، "
        "ولا تقدمه كأنه يحدد مال القارئ مباشرة.\n"
        "- ممنوع استخدام مفارقة جغرافية صادمة لتبسيط علاقة اقتصادية معقدة. مثال مرفوض: "
        "«قسطك مرتبط بقرار في واشنطن مو الرياض». هذه جملة مثيرة لكنها مضللة وغير مريحة.\n"
        "- بدلاً من ذلك، اجعل الفضول في سؤال عملي واضح، مثل: «ليش فائدة أمريكا تهم "
        "التمويل هنا؟» ثم اشرح الآلية بجمل قصيرة.\n"
        "- إذا كان الأثر يختلف حسب المنتج أو العقد، لا تخاطب الجميع كأن النتيجة واحدة. "
        "قل مثلاً: «إذا كان تمويلك متغيراً...» ثم وضّح ما الذي يحدد الأثر فعلياً.\n"
        "- في موضوع الفيدرالي والسعودية: اشرح أن ارتباط الريال بالدولار يجعل السياسة "
        "النقدية والفائدة المحلية تتأثر بتحركات الفائدة الأمريكية، لكن تكلفة التمويل "
        "الفعلية تعتمد على الفائدة المحلية ونوع المنتج وتسعير البنك وشروط العقد. لا تقل "
        "إن الفيدرالي «يحدد قسطك» أو إن قراره «يوصلك خلال أيام».\n"
        "- ابدأ بما يستطيع المتابع فهمه أو استخدامه: ما الذي قد يتغير هنا؟ من يتأثر؟ "
        "وماذا يراجع في عقده أو في الفائدة المحلية؟ الجاذبية تأتي من الفائدة العملية "
        "والمعلومة الدقيقة، لا من المبالغة.\n"
    )
    return prompt
