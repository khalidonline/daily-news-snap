"""Editorial policy and candidate preparation for the Saudi Snapchat daily brief.

This module deliberately contains no publishing or rendering code.  It owns the
feed registry, conservative audience-fit filtering, freshness metadata helpers,
lane-balanced shortlist construction, and the system prompt used by the daily
editor.
"""

from collections import defaultdict, deque
from pathlib import Path
from datetime import datetime, timedelta, timezone
import re
import sys
from xml.etree import ElementTree as ET

DEFAULT_LOOKBACK_HOURS = 48
MAX_NORMAL_AGE_HOURS = 48

LANE_TARGETS = {
    "business_tech": 20,
    "saudi_core": 16,
    "sports": 8,
    "entertainment_culture": 8,
    "travel_lifestyle": 8,
}

FEED_SPECS = (
    # Global business / technology sources.
    {"source": "BBC", "url": "https://feeds.bbci.co.uk/news/business/rss.xml", "lane": "business_tech"},
    {"source": "BBC", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "lane": "business_tech"},
    {"source": "TechCrunch", "url": "https://techcrunch.com/feed/", "lane": "business_tech"},
    {"source": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "lane": "business_tech"},
    {"source": "Engadget", "url": "https://www.engadget.com/rss.xml", "lane": "business_tech"},
    {"source": "CNBC", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "lane": "business_tech"},
    {"source": "CNBC", "url": "https://www.cnbc.com/id/19854910/device/rss/rss.html", "lane": "business_tech"},
    # Saudi/Gulf core: use specific national/economy sections instead of broad
    # general-news feeds that are dominated by politics, conflict, or hyperlocal noise.
    {"source": "اليوم", "url": "https://www.alyaum.com/rssFeed/1005/92", "lane": "saudi_core"},
    {"source": "اليوم", "url": "https://www.alyaum.com/rssFeed/1006", "lane": "saudi_core"},
    {"source": "الوطن", "url": "https://www.alwatan.com.sa/rssFeed/4", "lane": "saudi_core"},
    {"source": "الشرق الأوسط", "url": "https://aawsat.com/feed/gulf", "lane": "saudi_core"},
    {"source": "الشرق الأوسط", "url": "https://aawsat.com/feed/economy", "lane": "saudi_core"},
    # Dedicated Saudi-interest sports.
    {"source": "اليوم", "url": "https://www.alyaum.com/rssFeed/1009", "lane": "sports"},
    {"source": "اليوم", "url": "https://www.alyaum.com/rssFeed/1009/112", "lane": "sports"},
    {"source": "الوطن", "url": "https://www.alwatan.com.sa/rssFeed/3", "lane": "sports"},
    {"source": "الشرق الأوسط", "url": "https://aawsat.com/feed/sport", "lane": "sports"},
    # Entertainment / culture.
    {"source": "اليوم", "url": "https://www.alyaum.com/rssFeed/1008", "lane": "entertainment_culture"},
    {"source": "الوطن", "url": "https://www.alwatan.com.sa/rssFeed/10", "lane": "entertainment_culture"},
    {"source": "الشرق الأوسط", "url": "https://aawsat.com/feed/culture", "lane": "entertainment_culture"},
    {"source": "الشرق الأوسط", "url": "https://aawsat.com/feed/arts", "lane": "entertainment_culture"},
    {"source": "الشرق الأوسط", "url": "https://aawsat.com/feed/cinema", "lane": "entertainment_culture"},
    # Travel / lifestyle.
    {"source": "اليوم", "url": "https://www.alyaum.com/rssFeed/1007/105", "lane": "travel_lifestyle"},
    {"source": "الشرق الأوسط", "url": "https://aawsat.com/feed/travel", "lane": "travel_lifestyle"},
    {"source": "اليوم", "url": "https://www.alyaum.com/rssFeed/1007", "lane": "travel_lifestyle"},
)

# The deterministic gates are intentionally conservative. Nuanced ranking
# belongs to the model; these remove only material that is outside the product's
# agreed scope or obviously too routine to consume model capacity.
_LOCAL_ROUTINE_RE = re.compile(
    r"(?:بلدية|أمانة|حي\b|حديقة|ممشى|تشجير|سفلتة|إنارة|دوار|مواقف)"
)
_BROAD_RELEVANCE_RE = re.compile(
    r"(?:السعودية|المملكة|ساما|وزارة|هيئة|مطار|طيران|تأشيرة|تمويل|قرض|"
    r"رهن|إسكان|أسعار|رسوم|ضريبة|بنك|موسم الرياض|نيوم|القدية|العلا|"
    r"الهلال|النصر|الاتحاد|الأهلي|المنتخب)"
)
_ROUTINE_PR_RE = re.compile(
    r"(?:بحث(?:ا|ت|وا)?\s+(?:أوجه\s+)?التعاون|مذكرة تفاهم|اجتماع.*التعاون|"
    r"استعراض فرص التعاون|تعزيز أوجه التعاون)"
)
_ROUTINE_SPORTS_RE = re.compile(
    r"(?:موعد مباراة|تشكيلة المباراة|التشكيل المتوقع|نتيجة المباراة|مواعيد مباريات)"
)
_IMPACT_RE = re.compile(
    r"(?:إطلاق|إلغاء|خفض|رفع|زيادة|انخفاض|سعر|رسوم|قرار|نظام|تمويل|"
    r"استحواذ|اكتتاب|تأشيرة|رحلات|مطار|مليار|مليون|%|صفقة كبرى|بطولة كبرى)"
)

_DIRECT_SAUDI_RE = re.compile(
    r"(?:السعودي(?:ة|ين|ون)?|المملكة العربية السعودية|المملكة|ساما|أرامكو|"
    r"الرياض|جدة|الخليج|مجلس التعاون|Saudi|KSA|Riyadh|Jeddah|Gulf|GCC)",
    re.IGNORECASE,
)
_NEGATED_SAUDI_RE = re.compile(
    r"(?:بعيد(?:ة)?\s+عن\s+(?:السعودية|المملكة|الخليج)|"
    r"لا\s+(?:يؤثر|يمس|يرتبط)\s+[^.]{0,30}(?:بالسعودية|بالخليج|السعودية|الخليج)|"
    r"دون\s+(?:أثر|تأثير)\s+[^.]{0,30}(?:السعودية|الخليج)|"
    r"(?:no|without)\s+(?:direct\s+)?(?:impact|effect|relevance)\s+(?:on|to)\s+"
    r"(?:Saudi Arabia|Saudi|KSA|the Gulf|Gulf|GCC))",
    re.IGNORECASE,
)
_SAUDI_IMPACT_RE = re.compile(
    r"(?:رسوم|تعرفة|صادرات|واردات|تجارة|استثمار|عقود|نفط|إنتاج|أسعار|"
    r"فائدة|تمويل|بنوك|تأشيرة|رحلات|طيران|سفر|ضريبة|تكلفة|وظائف|"
    r"tariff|fees?|exports?|imports?|trade|investment|contracts?|oil|production|"
    r"prices?|interest rates?|financing|banks?|visa|flights?|aviation|travel|tax|cost|jobs?)",
    re.IGNORECASE,
)
_FOREIGN_POLITICS_RE = re.compile(
    r"(?:ترامب|بايدن|بوتين|زيلينسكي|مادورو|نتنياهو|أردوغان|خامنئي|"
    r"انتخابات|عقوبات|دبلوماس(?:ي|ية)|جيوسياس(?:ي|ية)|حرب|صراع|نزاع|"
    r"وقف إطلاق النار|Trump|Biden|Putin|Zelensky|Maduro|Netanyahu|Erdogan|"
    r"Khamenei|elections?|sanctions?|diplomat(?:ic|y)|geopolitic(?:al|s)|"
    r"\bwar\b|\bconflict\b|ceasefire)",
    re.IGNORECASE,
)
_MEDICAL_RE = re.compile(
    r"(?:ضغط الدم|أدوية?|دواء|علاج|مرض|أعراض|طبيب|مرضى|سرطان|سكري|"
    r"كوليسترول|جرعة|لقاح|نصيحة طبية|نصائح طبية|blood pressure|medication|"
    r"medicine|treatment|disease|symptoms?|doctor|patients?|cancer|diabetes|"
    r"cholesterol|dosage|vaccine|medical advice)",
    re.IGNORECASE,
)
_PERSONAL_MEDICAL_ADVICE_RE = re.compile(
    r"(?:"
    r"(?:هل|كيف|ماذا)\s+[^.؟?]{0,100}(?:يضر|يفيد|يسبب|يرفع|يخفض|يحمي|يؤثر|مفيد|ضار|آمن)"
    r"[^.؟?]{0,60}(?:الكبد|الكلى|القلب|الجسم|الصحة|النوم|الوزن|المناعة|السكر|الضغط)|"
    r"(?:لا\s+دليل\s+على\s+أن|ينفي\s+أن|تنفي\s+أن)\s+[^.؟?]{0,100}"
    r"(?:يضر|يفيد|يسبب|يرفع|يخفض|يحمي|يؤثر)[^.؟?]{0,60}"
    r"(?:الكبد|الكلى|القلب|الجسم|الصحة|النوم|الوزن|المناعة|السكر|الضغط)|"
    r"(?:حقيقة\s+)?(?:تأثير|أثر|فوائد|أضرار)\s+[^.؟?]{0,100}(?:على|لـ)\s*"
    r"(?:الكبد|الكلى|القلب|الجسم|الصحة|النوم|الوزن|المناعة|السكر|الضغط)|"
    r"(?:نصيحة طبية|نصائح صحية|فوائد صحية|أضرار صحية)|"
    r"(?:does|can|could|how)\s+[^.?]{0,100}(?:harm|help|cause|lower|raise|protect|affect)"
    r"[^.?]{0,60}(?:liver|kidney|heart|body|health|sleep|weight|immunity|blood sugar|blood pressure)|"
    r"(?:effect|impact|benefits?|risks?)\s+of\s+[^.?]{0,80}\s+on\s+"
    r"(?:liver|kidney|heart|body|health|sleep|weight|immunity|blood sugar|blood pressure)|"
    r"(?:health tips?|health benefits?|health risks?)"
    r")",
    re.IGNORECASE,
)
_HEALTH_POLICY_RE = re.compile(
    r"(?:تأمين|تغطية|نظام|قرار|أسعار|رسوم|خدمة|وزارة الصحة|مستشفى|"
    r"insurance|coverage|policy|regulation|pricing|fees?|health ministry|hospital)",
    re.IGNORECASE,
)
_WEATHER_RE = re.compile(
    r"(?:أمطار|طقس|درجات الحرارة|رياح|غبار|برد|عاصفة|ضباب|موجة حارة|"
    r"سحب رعدية|weather|rain|thunderstorm|temperature|dust storm|fog|heatwave)",
    re.IGNORECASE,
)
_MATERIAL_DISRUPTION_RE = re.compile(
    r"(?:تغلق|يغلق|إغلاق|تلغي|إلغاء|تعليق|توقف|تعطل|تأجيل)"
    r"[^.]{0,60}(?:مطار|رحلات|طيران|مدارس|دراسة|طرق|خدمات|airport|flights?|"
    r"aviation|schools?|roads?|services?)|"
    r"(?:مطار|رحلات|طيران|مدارس|دراسة|طرق|خدمات|airport|flights?|aviation|"
    r"schools?|roads?|services?)[^.]{0,60}"
    r"(?:تغلق|يغلق|إغلاق|تلغي|إلغاء|تعليق|توقف|تعطل|تأجيل|closed?|cancel|"
    r"suspend|disrupt|delay)",
    re.IGNORECASE,
)
_ACCIDENT_EVENT_RE = re.compile(
    r"(?:حادث|حوادث|توفي|وفاة|مقتل|قتلى|إصابة|إصابات|مصاب|مصابين|اصطدام|"
    r"تحطم|دهس|كارثة|اضطراب جوي[^.]{0,80}(?:وفاة|توفي|إصابة|دعوى)|"
    r"accidents?|fatal(?:ity|ities)?|\bdied\b|\bdeath\b|\bkilled\b|collision|"
    r"(?:plane|aircraft) crash|turbulence[^.]{0,80}(?:death|died|injur|lawsuit))",
    re.IGNORECASE,
)
_SAFETY_RULE_CHANGE_RE = re.compile(
    r"(?:قواعد|لائحة|لوائح|معايير|اشتراطات|قرار تنظيمي|نظام جديد|تنظيم جديد|"
    r"تلزم|إلزام|rules?|regulations?|standards?|requirements?|mandate)",
    re.IGNORECASE,
)
_ROUTINE_RESULT_RE = re.compile(
    r"(?:يسحق|يهزم|يتغلب|يفوز|فاز|خسر|تعادل|يتعادل|بخماسية|برباعية|"
    r"بثلاثية|نتيجة\s+(?:المباراة|اللقاء)|انتهت المباراة|\b\d+\s*[-–:]\s*\d+\b|"
    r"\bbeats?\b|\bdefeats?\b|\bwins?\b|\bloses?\b|\bdraws?\b|final score)",
    re.IGNORECASE,
)
_MAJOR_SPORTS_RE = re.compile(
    r"(?:نهائي|النهائي|يتوج|توج|بطولة|كأس العالم|دوري أبطال|كأس آسيا|"
    r"يتأهل|التأهل|لقب|رقم قياسي|تاريخي|ميدالية|final|champion|championship|"
    r"world cup|champions league|qualif(?:y|ies|ied|ication)|title|record|historic|medal)",
    re.IGNORECASE,
)
_UNCONFIRMED_TRANSFER_RE = re.compile(
    r"(?:"
    r"(?:تقارير|مصادر|أنباء)[^.\n]{0,160}(?:انتقال|التعاقد|صفقة|ضم|انضمام|الانضمام)|"
    r"(?:يقترب|قريب|مرشح|مفاوضات|يتفاوض|قرب|في\s+طريقه|في\s+طريقها)[^.\n]{0,100}(?:انتقال|التعاقد|صفقة|ضم|انضمام|الانضمام)|"
    r"(?:انتقال|التعاقد|صفقة|ضم|انضمام|الانضمام)[^.\n]{0,100}(?:يقترب|قريب|مرشح|مفاوضات|يتفاوض|قرب|في\s+طريقه|في\s+طريقها)|"
    r"(?:reports?|sources?)[^.\n]{0,160}(?:transfer|sign|move|join)|"
    r"(?:close to|set to|linked with|in talks|on (?:his|her|the) way)[^.\n]{0,100}(?:transfer|sign|move|join)|"
    r"(?:transfer|sign|move|join)[^.\n]{0,100}(?:close to|set to|linked with|in talks|on (?:his|her|the) way)"
    r")",
    re.IGNORECASE,
)
_FINANCING_RE = re.compile(
    r"(?:تقترض|اقتراض|قرض|تمويل|جولة تمويل|تجمع\s+[^.]{0,40}(?:مليون|مليار)|"
    r"ديون|borrows?|loan|funding round|raises?\s+\$|raises?\s+[^.]{0,20}\b(?:million|billion)\b|"
    r"debt financing|debt facility)",
    re.IGNORECASE,
)
_SUBJECT_LATIN_RE = re.compile(r"^\s*(?:شركة\s+)?([A-Za-z][A-Za-z0-9.&+\-]{1,40})\b")
_KNOWN_GLOBAL_COMPANIES = {
    "alphabet", "amazon", "anthropic", "apple", "boeing", "bytedance",
    "disney", "google", "meta", "microsoft", "netflix", "nvidia",
    "openai", "samsung", "snap", "spacex", "tesla", "tiktok", "uber",
}

_XML_ILLEGAL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_BARE_AMP_RE = re.compile(
    r"&(?!#\d+;|#x[0-9A-Fa-f]+;|[A-Za-z][A-Za-z0-9]+;)"
)
_FIRST_FEED_CLOSE_RE = re.compile(r"</(?:rss|feed)\s*>", re.IGNORECASE)


def hard_scope_eligible(item):
    """Enforce non-negotiable daily scope before the model can rank a story.

    This is deliberately a rejection gate, not a scoring engine. Ambiguous but
    plausible stories are left for the editorial model; only known product-scope
    violations are removed here.
    """
    title = str(item.get("title", "") or "").strip()
    summary = str(item.get("summary", "") or "").strip()
    text = f"{title} {summary}".strip()
    lane = item.get("lane", "business_tech")
    direct_saudi = bool(_DIRECT_SAUDI_RE.search(text)) and not _NEGATED_SAUDI_RE.search(text)
    direct_saudi_impact = direct_saudi and bool(_SAUDI_IMPACT_RE.search(text))

    # Remote politics/geopolitics is outside this product. Merely naming Saudi
    # Arabia is not enough; the input itself must contain a concrete Saudi/Gulf
    # economic, consumer, travel or employment consequence.
    if _FOREIGN_POLITICS_RE.search(text) and not direct_saudi_impact:
        return False

    # Personal health advice stays outside the product even when a ministry or
    # hospital is quoted. A named authority is evidence provenance, not proof
    # that the story is a national policy or service change.
    if _PERSONAL_MEDICAL_ADVICE_RE.search(text):
        return False

    # Other medical content is excluded unless it is a broad Saudi
    # policy/insurance/service change that affects adult daily life.
    if _MEDICAL_RE.search(text):
        if not (lane == "saudi_core" and direct_saudi and _HEALTH_POLICY_RE.search(text)):
            return False

    # Routine forecasts belong in a weather product. A weather event that is
    # fundamentally a material transport/school/service disruption can qualify.
    if _WEATHER_RE.search(text) and not _MATERIAL_DISRUPTION_RE.search(text):
        return False

    # Accident/death/disaster event coverage is outside the approved daily brief.
    # A genuinely national Saudi safety-rule change can still qualify even when
    # the article mentions the incident that triggered the regulation.
    if _ACCIDENT_EVENT_RE.search(text):
        if not (direct_saudi and _SAFETY_RULE_CHANGE_RE.search(text)):
            return False

    # Transfer speculation is still a rumor even when the sentence says the
    # eventual move would be "official". A club announcement/confirmed deal has
    # no proximity/negotiation wording and remains eligible.
    if lane == "sports" and _UNCONFIRMED_TRANSFER_RE.search(text):
        return False

    # Ordinary match recaps never consume a national card; major titles,
    # qualification, finals and records remain eligible.
    if lane == "sports" and _ROUTINE_RESULT_RE.search(text) and not _MAJOR_SPORTS_RE.search(text):
        return False

    # Large funding numbers and a famous chip/vendor name should not make an
    # unfamiliar startup into mainstream news for this audience.
    if lane == "business_tech" and _FINANCING_RE.search(text) and not direct_saudi:
        subject = _SUBJECT_LATIN_RE.search(title)
        if subject and subject.group(1).casefold() not in _KNOWN_GLOBAL_COMPANIES:
            return False

    return True


def audience_fit_eligible(item):
    """Reject only obvious routine/hyperlocal noise before lane allocation."""
    text = f"{item.get('title', '')} {item.get('summary', '')}".strip()
    lane = item.get("lane", "business_tech")

    if _ROUTINE_PR_RE.search(text) and not _IMPACT_RE.search(text):
        return False
    if lane == "saudi_core" and _LOCAL_ROUTINE_RE.search(text) and not _BROAD_RELEVANCE_RE.search(text):
        return False
    if lane == "sports" and _ROUTINE_SPORTS_RE.search(text) and not _IMPACT_RE.search(text):
        return False
    return True


def publication_age_hours(item, now=None):
    raw = item.get("published_at")
    if not raw:
        return None
    try:
        published = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age = (now.astimezone(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() / 3600
    return max(0.0, age)


def format_age_label(item, now=None):
    age = publication_age_hours(item, now=now)
    return "unknown" if age is None else f"{int(age)}h"


def freshness_eligible(item, now=None, max_age_hours=MAX_NORMAL_AGE_HOURS):
    age = publication_age_hours(item, now=now)
    return age is not None and age <= max_age_hours


def _title_key(title):
    return re.sub(r"\W+", "", (title or "").casefold())[:120]


def _dedupe_candidates(items):
    seen = set()
    result = []
    for item in items:
        key = _title_key(item.get("title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _published_sort_value(item):
    raw = item.get("published_at")
    if not raw:
        return float("-inf")
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (TypeError, ValueError):
        return float("-inf")


def _lane_source_queues(items):
    by_lane = defaultdict(lambda: defaultdict(list))
    for item in items:
        by_lane[item.get("lane", "business_tech")][item.get("source", "unknown")].append(item)
    result = defaultdict(dict)
    for lane, sources in by_lane.items():
        for source, source_items in sources.items():
            source_items.sort(key=_published_sort_value, reverse=True)
            result[lane][source] = deque(source_items)
    return result


def _pop_lane_item(source_queues, cursor):
    sources = list(source_queues)
    if not sources:
        return None, cursor
    for offset in range(len(sources)):
        idx = (cursor + offset) % len(sources)
        source = sources[idx]
        queue = source_queues[source]
        if queue:
            return queue.popleft(), (idx + 1) % len(sources)
    return None, cursor


def balanced_shortlist(items, limit=60, now=None):
    """Build a source-fair shortlist with lane targets and spillover.

    Targets are opportunities, never quotas. Empty/weak lanes may contribute
    zero and unused capacity is redistributed. Freshness only orders otherwise
    comparable items inside a source; it does not displace a strong older lane
    candidate with unrelated weak material.
    """
    qualified = [
        item for item in items
        if hard_scope_eligible(item)
        and audience_fit_eligible(item)
        and freshness_eligible(item, now=now)
    ]
    qualified = _dedupe_candidates(qualified)
    queues = _lane_source_queues(qualified)
    lane_order = [lane for lane in LANE_TARGETS if queues.get(lane)]
    cursors = {lane: 0 for lane in lane_order}
    counts = defaultdict(int)
    selected = []

    progress = True
    while len(selected) < limit and progress:
        progress = False
        for lane in lane_order:
            if len(selected) >= limit:
                break
            if counts[lane] >= LANE_TARGETS[lane]:
                continue
            item, cursors[lane] = _pop_lane_item(queues[lane], cursors[lane])
            if item is not None:
                selected.append(item)
                counts[lane] += 1
                progress = True

    progress = True
    while len(selected) < limit and progress:
        progress = False
        for lane in lane_order:
            if len(selected) >= limit:
                break
            item, cursors[lane] = _pop_lane_item(queues[lane], cursors[lane])
            if item is not None:
                selected.append(item)
                counts[lane] += 1
                progress = True

    return selected


def shortlist_lane_counts(items):
    counts = defaultdict(int)
    for item in items:
        counts[item.get("lane", "business_tech")] += 1
    return dict(counts)


def decorate_model_items(items, now=None):
    """Copy candidates and add internal lane/age tags to the supplied summary.

    The public source/title/link fields stay unchanged. The system prompt tells
    the model these bracketed tags are metadata and must never be copied to card
    text.
    """
    result = []
    for item in items:
        copy = dict(item)
        summary = copy.get("summary", "")
        copy["summary"] = (
            f"[lane={copy.get('lane', 'business_tech')}] "
            f"[age={format_age_label(copy, now=now)}] {summary}"
        ).strip()
        result.append(copy)
    return result


def _parse_feed_root(raw):
    """Parse a feed strictly, then retry only conservative syntax recovery.

    Recovery is intentionally bounded: strip XML-illegal controls, escape bare
    ampersands, and—only after parsing still fails—truncate trailing content
    after the first complete RSS/Atom root. This recovers publishers that
    accidentally concatenate two documents without trying to invent markup.
    """
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        text = _XML_ILLEGAL_RE.sub("", text)
        text = _BARE_AMP_RE.sub("&amp;", text)
        try:
            return ET.fromstring(text)
        except ET.ParseError:
            match = _FIRST_FEED_CLOSE_RE.search(text)
            if not match:
                raise
            return ET.fromstring(text[:match.end()])


def fetch_headlines(http_get, clean, parse_date, *, feed_specs=FEED_SPECS,
                    lookback_hours=DEFAULT_LOOKBACK_HOURS, now=None):
    """Fetch lane-tagged RSS/Atom items using news_bot's existing HTTP helpers."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=lookback_hours)
    items, seen = [], set()

    for feed in feed_specs:
        source, url, lane = feed["source"], feed["url"], feed["lane"]
        try:
            root = _parse_feed_root(http_get(url))
        except Exception as exc:
            print(f"  ! {source}: {exc}", file=sys.stderr)
            print(f"  {source}: 0 items (failed)")
            continue

        entries = root.iter("item") if root.find(".//item") is not None else \
            root.iter("{http://www.w3.org/2005/Atom}entry")
        count = 0
        for entry in entries:
            def field(*names):
                for name in names:
                    el = entry.find(name)
                    if el is not None:
                        return el.text or el.get("href") or ""
                return ""

            title = clean(field("title", "{http://www.w3.org/2005/Atom}title"))
            if not title:
                continue
            key = re.sub(r"\s", "", title)[:60]
            if key in seen:
                continue

            published = parse_date(field(
                "pubDate", "{http://www.w3.org/2005/Atom}updated",
                "{http://www.w3.org/2005/Atom}published"))
            if published is None:
                continue
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published < cutoff:
                continue

            seen.add(key)
            items.append({
                "source": source,
                "lane": lane,
                "title": title,
                "summary": clean(field(
                    "description", "{http://www.w3.org/2005/Atom}summary"))[:400],
                "link": field("link", "{http://www.w3.org/2005/Atom}link"),
                "published_at": published.astimezone(timezone.utc).isoformat(),
            })
            count += 1
        print(f"  {source}: {count} recent items")
    return items


_PROMPT_PATH = Path(__file__).with_name("news_editorial_prompt.txt")
SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")
