#!/usr/bin/env python3
"""
موضوع اليوم — بحث وتحليل -> سناب شات
Topic research mode.

You give it a topic. Claude searches the web (server-side web_search tool),
analyses what it finds, and returns a short Arabic brief. Rendered as one
card and posted the same way as the news bot.

    TOPIC="مستقبل الطاقة المتجددة في السعودية" python topic_bot.py

Reuses the fetch/post/render plumbing from news_bot.py.
"""

import json
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from news_bot import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL, DRY_RUN, MEDIA_MODE, OUT_DIR,
    W, H, BG_TOP, BG_BOTTOM, ACCENT, TEXT, MUTED, AR_DIGITS,
    ar, load_font, _wrap,
    publish_via_github, upload_media, post_story,
    fetch_headlines, commit_and_push,
)

TOPIC = os.getenv("TOPIC", "").strip()
TOPICS_FILE = Path(os.getenv("TOPICS_FILE", "topics.txt"))
VOICE_FILE = Path(os.getenv("VOICE_FILE", "voice.txt"))


def load_voice():
    """Sample lines showing the register to imitate. Empty file = no examples."""
    try:
        lines = VOICE_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    return [ln.strip() for ln in lines
            if ln.strip() and not ln.strip().startswith("#")]


def load_topics():
    """Topics from topics.txt, ignoring blanks and # comments."""
    if not TOPICS_FILE.exists():
        here = sorted(p.name for p in Path(".").iterdir() if p.is_file())
        print(f"  ! {TOPICS_FILE} not found. Files here: {', '.join(here)}")
        return []
    lines = TOPICS_FILE.read_text(encoding="utf-8").splitlines()
    topics = [ln.strip() for ln in lines
              if ln.strip() and not ln.strip().startswith("#")]
    if not topics:
        print(f"  ! {TOPICS_FILE} has {len(lines)} lines but none usable "
              "— are they all comments?")
    return topics


USED_FILE = Path("state/topics_used.json")
COOLDOWN_DAYS = int(os.getenv("COOLDOWN_DAYS", "21"))
HARD_COOLDOWN_DAYS = int(os.getenv("HARD_COOLDOWN_DAYS", "5"))
SELECT_MODEL = os.getenv("SELECT_MODEL", "claude-sonnet-5")


def load_used():
    """Topics covered recently, so the picker doesn't repeat itself."""
    try:
        data = json.loads(USED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    cutoff = (datetime.now() - timedelta(days=COOLDOWN_DAYS)).isoformat()
    return [e for e in data if e.get("at", "") >= cutoff]


def save_used(previous, topic):
    USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    entries = previous + [{"topic": topic, "at": datetime.now().isoformat()}]
    USED_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    return USED_FILE


SELECT_PROMPT = """أنت محرر تختار موضوع اليوم لموجز يُنشر على سناب شات لجمهور سعودي.

ستصلك قائمة مواضيع مرقّمة، وعناوين أخبار الأمس. اختر الموضوع الأكثر ارتباطاً \
بما يشغل الناس الآن بناءً على تلك العناوين.

معايير الاختيار:
- الموضوع الذي تلمسه أخبار الأمس مباشرة يسبق غيره.
- الموضوع الذي يجيب على سؤال يطرحه الناس بعد قراءة تلك الأخبار.
- إن لم يرتبط أي موضوع بالأخبار، اختر الأكثر أهمية للقارئ السعودي عموماً.
- المواضيع في قائمة "استُخدمت مؤخراً" ليست ممنوعة: يجوز إعادة أحدها إذا كانت \
أخبار الأمس تعيده بقوة إلى الواجهة وتضيف إليه جديداً. غير ذلك، فضّل موضوعاً جديداً.

أجب بصيغة JSON فقط: {"index": رقم الموضوع, "why": "سبب الاختيار في جملة قصيرة"}"""


def choose_topic():
    """Pick the topic that best fits yesterday's news."""
    topics = load_topics()
    if not topics:
        return ""

    used = load_used()
    hard_cutoff = (datetime.now() - timedelta(days=HARD_COOLDOWN_DAYS)).isoformat()
    blocked = {e["topic"] for e in used if e.get("at", "") >= hard_cutoff}
    recent = {e["topic"] for e in used} - blocked

    available = [(i, t) for i, t in enumerate(topics) if t not in blocked]
    if not available:
        available = list(enumerate(topics))

    print(f"    {len(available)} topics available "
          f"({len(blocked)} on cooldown, {len(recent)} recently used)")
    print("    reading yesterday's headlines to pick a topic...")
    try:
        items = fetch_headlines()
    except Exception as exc:
        print(f"  ! couldn't fetch headlines ({exc}) — falling back to rotation")
        items = []

    if not items or not ANTHROPIC_API_KEY:
        index, topic = available[datetime.now().toordinal() % len(available)]
        print(f"    fallback rotation -> {topic}")
        return topic

    listing = "\n".join(f"{i}. {t}" for i, t in available)
    headlines = "\n".join(f"- {i['title']}" for i in items[:50])
    recent_list = "\n".join(f"- {t}" for t in recent) or "لا يوجد"

    payload = {
        "model": SELECT_MODEL,
        "max_tokens": 500,
        "system": SELECT_PROMPT,
        "messages": [{"role": "user", "content":
                      f"المواضيع المتاحة:\n{listing}\n\n"
                      f"عناوين الأمس:\n{headlines}\n\n"
                      f"استُخدمت مؤخراً:\n{recent_list}"}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json",
                 "x-api-key": ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
        start, end = text.find("{"), text.rfind("}")
        choice = json.loads(text[start:end + 1])
        topic = topics[int(choice["index"])]
        print(f"    chose: {topic}")
        print(f"    why:   {choice.get('why', '')}")
        return topic
    except Exception as exc:
        print(f"  ! topic selection failed ({exc}) — falling back to rotation")
        index, topic = available[datetime.now().toordinal() % len(available)]
        print(f"    fallback rotation -> {topic}")
        return topic
TOPIC_MODEL = os.getenv("TOPIC_MODEL", "claude-opus-5")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
HERO_HEIGHT = int(os.getenv("HERO_HEIGHT", "620"))


USER_AGENT = "Mozilla/5.0 (compatible; daily-news-bot/1.0)"

KICKER = os.getenv("KICKER", "ملخص تنفيذي")

IMAGE_SOURCE = os.getenv("IMAGE_SOURCE", "none").strip()
# openverse (free, no key) | article (publisher photo) | stock (Pexels, needs key) | none

OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE)
OG_IMAGE_ALT_RE = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']',
    re.IGNORECASE)


def fetch_article_photo(url, out_path):
    """Pull the lead photo an article publishes in its og:image tag.

    IMPORTANT: that photo belongs to the publisher. Only use this for sources
    whose terms permit republication, and always show the credit the card
    renders from the returned domain.
    Returns (path, domain) or (None, None).
    """
    if not url:
        return None, None

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read(400_000).decode("utf-8", "ignore")
    except Exception as exc:
        print(f"  ! couldn't read {url}: {exc}")
        return None, None

    match = OG_IMAGE_RE.search(html) or OG_IMAGE_ALT_RE.search(html)
    if not match:
        print(f"  ! no og:image on {url}")
        return None, None

    img_url = urllib.parse.urljoin(url, match.group(1))
    domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
    try:
        req = urllib.request.Request(img_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        if len(data) < 15_000:
            print("  ! og:image too small — probably a logo, skipping")
            return None, None
        Path(out_path).write_bytes(data)
    except Exception as exc:
        print(f"  ! photo download failed: {exc}")
        return None, None

    print(f"    photo: article image from {domain}")
    return str(out_path), domain


DOMAIN_CREDITS = {
    "spa.gov.sa": "واس",
    "argaam.com": "أرقام",
    "aawsat.com": "الشرق الأوسط",
    "alarabiya.net": "العربية",
    "okaz.com.sa": "عكاظ",
    "alyaum.com": "اليوم",
}


def _openverse_search(query, page_size=12):
    """Search Openverse for openly licensed images. No API key needed.

    Anonymous access is rate limited, so a 429 here is normal on repeat runs.
    """
    url = ("https://api.openverse.org/v1/images/"
           f"?q={urllib.parse.quote(query)}&page_size={page_size}"
           "&license_type=commercial,modification&mature=false")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            results = json.loads(resp.read()).get("results", [])
        print(f"    Openverse: {len(results)} results for {query!r}")
        return results
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            print("  ! Openverse rate limited (anonymous quota) — try again later")
        else:
            print(f"  ! Openverse HTTP {exc.code} for {query!r}")
        return []
    except Exception as exc:
        print(f"  ! Openverse error for {query!r}: {exc}")
        return []


def _ov_score(item, terms):
    text = " ".join(filter(None, [
        item.get("title") or "",
        " ".join(t.get("name", "") for t in item.get("tags") or []),
    ])).lower()
    if not text:
        return 0
    hits = sum(1 for t in terms if t in text)
    wide = (item.get("width") or 0) >= (item.get("height") or 1)
    return hits * 10 + (3 if wide else 0)


def fetch_openverse_photo(queries, out_path):
    """Fetch an openly licensed photo. Returns (path, credit) or (None, None).

    Only commercial-use, modification-allowed licences are requested, and the
    creator and licence are returned so the card can credit them.
    """
    if isinstance(queries, str):
        queries = [queries]
    queries = [q.strip() for q in queries if q and q.strip()]
    if not queries:
        return None, None

    candidates = []
    for query in queries:
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        results = _openverse_search(query)
        if not results:
            continue
        for item in results:
            candidates.append((_ov_score(item, terms), query, item))
        if any(c[0] >= 10 for c in candidates):
            break

    if not candidates:
        print("  ! no openly licensed photo found")
        return None, None

    candidates.sort(key=lambda c: -c[0])

    # work down the ranked list — one dead host shouldn't cost us the photo
    data, best, best_score, best_query = None, None, 0, None
    for score, query, item in candidates[:5]:
        for field in ("url", "thumbnail"):
            link = item.get(field)
            if not link:
                continue
            try:
                req = urllib.request.Request(link,
                                             headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=45) as resp:
                    payload = resp.read()
            except Exception as exc:
                print(f"  ! {field} failed ({exc}) — trying the next image")
                continue
            if len(payload) < 8_000:
                continue
            data, best, best_score, best_query = payload, item, score, query
            if field == "thumbnail":
                print("    (using Openverse thumbnail — original host refused)")
            break
        if data:
            break

    if data is None:
        print("  ! every Openverse candidate failed to download")
        return None, None
    Path(out_path).write_bytes(data)

    creator = (best.get("creator") or "").strip() or best.get("source", "Openverse")
    licence = (best.get("license") or "").upper()
    version = best.get("license_version") or ""
    credit = f"{creator} / CC {licence} {version}".strip()

    print(f"    photo: {best.get('title') or '(untitled)'} — {credit} "
          f"[{best_query}]")
    if best_score < 10:
        print("  ! weak match — the image may be only loosely related")
    return str(out_path), credit


def _pexels_search(query, per_page=12):
    url = (f"https://api.pexels.com/v1/search?per_page={per_page}"
           f"&orientation=landscape&query={urllib.parse.quote(query)}")
    req = urllib.request.Request(url, headers={"Authorization": PEXELS_API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("photos", [])
    except urllib.error.HTTPError as exc:
        print(f"  ! Pexels {exc.code} for {query!r}")
        return []
    except Exception as exc:
        print(f"  ! Pexels error for {query!r}: {exc}")
        return []


def _score(photo, terms):
    """How well does this photo's own description match what we asked for?"""
    alt = (photo.get("alt") or "").lower()
    if not alt:
        return 0
    hits = sum(1 for t in terms if t in alt)
    # a short, on-point caption beats a long one that happens to contain the word
    return hits * 10 - len(alt.split()) * 0.05


def fetch_photo(queries, out_path):
    """Fetch a licence-clear photo from Pexels, trying each query in turn and
    picking the result whose description best matches. Returns a path or None.

    Pexels images are free to use commercially without attribution. Never pull
    photos from news sites — those are licensed to the publisher.
    """
    if not PEXELS_API_KEY:
        print("  ! PEXELS_API_KEY not set — rendering without a photo")
        return None

    if isinstance(queries, str):
        queries = [queries]
    queries = [q.strip() for q in queries if q and q.strip()]
    if not queries:
        return None

    best, best_score, best_query = None, -999, None
    for query in queries:
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        photos = _pexels_search(query)
        if not photos:
            print(f"    no results for {query!r}")
            continue

        for photo in photos:
            score = _score(photo, terms)
            if score > best_score:
                best, best_score, best_query = photo, score, query

        # a clear match on an early (more specific) query wins outright
        if best_score >= 10:
            break

    if best is None:
        print("  ! no photo found — rendering without one")
        return None

    if best_score < 10:
        print(f"  ! weak photo match — using a generic image for {best_query!r}")

    src = best["src"].get("large2x") or best["src"]["large"]
    try:
        with urllib.request.urlopen(src, timeout=60) as resp:
            Path(out_path).write_bytes(resp.read())
    except Exception as exc:
        print(f"  ! photo download failed: {exc}")
        return None

    print(f"    photo: {best.get('alt') or '(no description)'} "
          f"— {best.get('photographer')} / Pexels [{best_query}]")
    return str(out_path)
MAX_SEARCHES = int(os.getenv("MAX_SEARCHES", "6"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "16000"))
POINTS = int(os.getenv("POINTS", "3"))


# --------------------------------------------------------------------------
# Research
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """أنت تكتب موجزاً يُنشر على سناب شات لجمهور سعودي عام.

سيعطيك المستخدم موضوعاً. ابحث في الإنترنت، ثم اكتب موجزاً يوقف القارئ عن التمرير: \
دقيق وموثّق، لكن بلغة قريبة وسهلة — لا لغة تقارير ولا بيانات رسمية.

الشكل المطلوب:
- title: عنوان لا يتجاوز ٤٥ حرفاً. يقول ما حدث، لا اسم الموضوع فقط. يجوز أن \
يتضمن رقماً محورياً مع وحدته.
- lead: جملة واحدة، لا تتجاوز ١٢٠ حرفاً. اجعلها الجملة التي تجعل القارئ \
يكمل: أهم ما في الموضوع، بصياغة تمسّه هو.
- points: {n} نقاط. كل نقطة:
  - heading: ٣ إلى ٥ كلمات تقول فكرة، لا عنواناً محايداً.
    ✗ "تراجع بعد ذروة الصيف"   ✓ "الهدوء الصيفي لم يدم"
  - text: جملتان قصيرتان، حتى ١٧٠ حرفاً — الإيجاز مطلوب. الجملة الأولى تقول ماذا حدث، \
والثانية تقول لماذا يهم أو ما الذي يترتب عليه.
- caption: نص المنشور المرافق، لا يتجاوز ١٢٠ حرفاً
- image_queries: ثلاث عبارات إنجليزية للبحث عن صورة، مرتبة من الأدق إلى الأعم.
  كل عبارة من كلمتين إلى أربع، وتصف شيئاً ملموساً يمكن تصويره — لا فكرة مجردة.
  ✗ "economic growth" أو "market analysis" (لا يمكن تصويرها)
  ✓ ["ripe dates closeup", "date palm harvest", "date fruit market"]
  الأولى تصف جوهر الموضوع نفسه، والثانية أوسع، والثالثة أعم ما يمكن.
  لا تذكر أشخاصاً بأعينهم ولا شعارات ولا علامات تجارية.
- sources: أسماء المصادر (٢ إلى ٤). إن كان المصدر أجنبياً فاكتبه بالعربية.
- source_url: رابط الخبر الرسمي الأدق الذي اعتمدت عليه (يفضَّل مصدر حكومي سعودي \
مثل واس أو موقع الجهة المعنية). ضع الرابط كاملاً كما ظهر في البحث.

قواعد الأسلوب — قريبة من الناس، لا رسمية:
- ابدأ بما يهم القارئ شخصياً، لا بالجهة التي أصدرت الخبر.
  ✗ "أعلنت الهيئة العامة للعقار تعديلاً على..."  ✓ "إيجارك قد يتغير السنة الجاية، وهذا السبب"
- خاطب القارئ مباشرة حين يناسب: "إذا كنت تفكر في شراء سيارة الآن..."
- جمل قصيرة. تجنّب التراكيب الطويلة والمبني للمجهول.
- استخدم كلمات الحياة اليومية بدل المصطلح المؤسسي: "تكلفة" لا "الكلفة التشغيلية".
- إن وُجدت أمثلة نبرة في نهاية هذه التعليمات فهي المرجع الأول للمستوى اللغوي.
  وإن لم توجد، فاكتب بفصحى مبسّطة قريبة من كلام الناس في السعودية.
- يجوز أن يكون العنوان سؤالاً أو مفارقة تجذب الانتباه — بشرط أن يكون صادقاً ولا يبالغ.
- ممنوع الحشو: "تجدر الإشارة"، "في هذا السياق"، "من الجدير بالذكر"، "وفي الختام".
- ممنوع الصفات الترويجية: هائل، مذهل، ضخم، تاريخي، غير مسبوق، ثورة.
- استخدم أفعالاً محايدة: تتغير، ترتفع، تنخفض، تزيد. وتجنّب الأفعال المبالِغة مثل: تقفز، تنهار، تشتعل، تتهاوى، تنفجر.
- لا تبدأ أكثر من نقطة واحدة برقم. الأرقام تدعم الفكرة ولا تحل محلها.
- كل نقطة تضيف زاوية جديدة، والأخيرة تجيب: ماذا يعني هذا لي؟
- انسب كل رقم لمصدره بعبارة قصيرة: "وفق أرقام وزارة..."، "بحسب تقرير...".
- لا تستخدم مصطلحاً مهنياً دون شرحه في نفس الجملة.

قواعد اللهجة والمصطلح — اكتب بلسان سعودي رسمي:
- قل "المملكة" لا "السعودية" في كل مرة، و"المواطنين" و"المقيمين" حين يلزم.
- استخدم الأسماء الرسمية للجهات: "المركز الوطني للنخيل والتمور"، "الهيئة العامة \
للإحصاء"، "وكالة الأنباء السعودية (واس)".
- استخدم أسماء المناطق كما تُستخدم محلياً: القصيم، المنطقة الشرقية، عسير، جازان.
- العملة ريال، واذكر "مليار ريال" لا "مليار دولار" إن كان المصدر بالريال.
- تجنّب التعابير المصرية أو الشامية أو المترجمة حرفياً عن الإنجليزية.
- التواريخ ميلادية بالأشهر العربية المعروفة في المملكة: يناير، فبراير، مارس...
- استخدم المفردات السعودية المألوفة، وتجنّب التعابير المصرية أو الشامية.

ممنوع منعاً باتاً:
- أي وسوم أو أقواس مراجع داخل النص مثل <cite> أو [1] أو (المصدر: ...).
- النص يجب أن يكون نصاً عربياً نظيفاً فقط. ضع أسماء المصادر في حقل sources وحده.

قواعد الدقة:
- اعتمد فقط على ما وجدته في البحث. لا تستخرج أرقاماً من ذاكرتك.
- إذا تضاربت المعلومات، قل ذلك واذكر التقديرين.
- إذا لم تجد ما يكفي، اجعل title هو "لا توجد معلومات كافية" واشرح السبب.

قبل أن تجيب، اقرأه كأنك رأيته في سناب شات: هل توقفت عنده أم مررت؟ هل يبدو \
كلاماً بشرياً أم بياناً رسمياً؟ وهل كل رقم منسوب لمصدره وله وحدة وتاريخ؟ \
إن كان أحد الجوابين لا، أعد الكتابة.

أجب بصيغة JSON فقط، بدون markdown وبدون مقدمة:
{{"title": "...", "lead": "...", "points": [{{"heading": "...", "text": "..."}}], \
"caption": "...", "image_queries": ["...", "...", "..."], \
"source_url": "...", "sources": ["...", "..."]}}"""


UNIT_WORDS = ("نقطة", "نقاط", "دولار", "دولاراً", "ريال", "ريالاً", "يورو",
              "مليون", "مليار", "ألف", "برميل", "برميلاً", "طن", "طناً", "كم",
              "متر", "يوم", "يوماً", "أيام", "شهر", "أشهر", "سنة", "سنوات",
              "أسبوع", "أسابيع", "ساعة", "حاوية", "قدماً", "بالمئة", "درجة",
              "عاماً", "عام", "سنوياً", "دقيقة", "كيلومتر", "كيلومترات",
              "هللة", "هللات", "كيلوواط", "ميغاواط", "جيجاواط", "واط",
              "لتر", "لتراً", "كيلو", "كيلوغرام", "غرام", "وحدة", "وحدات",
              "مقعد", "مقعداً", "شخص", "شخصاً", "زائر", "زائراً", "نسمة",
              "متراً", "أمتار", "هكتار", "مليونا", "مليارا")

MONTH_WORDS = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
               "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")


def warn_about_bare_numbers(brief):
    """Flag figures with neither a unit nor a date right after them —
    the reader can't tell whether 4,547 is dollars, points or something else."""
    for point in brief.get("points", []):
        text = point.get("text", "")
        for match in re.finditer(r"\d[\d,\.]*", text):
            token = match.group().rstrip(".,")
            if re.fullmatch(r"(19|20)\d{2}", token):
                continue                      # a year needs no unit
            tail = text[match.end():]
            if tail.startswith("%"):
                continue
            next_word = tail.strip().split(" ")[0].strip("،.:؛)") if tail.strip() else ""
            if next_word in UNIT_WORDS or next_word in MONTH_WORDS:
                continue
            print(f"  ! bare number {match.group()!r} in "
                  f"{point.get('heading')!r} — followed by {next_word!r}, "
                  f"no unit given")


CITE_RE = re.compile(r"</?cite[^>]*>", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]{1,80}>")


def strip_markup(value):
    """Remove citation tags and stray markup the model sometimes emits."""
    if isinstance(value, str):
        cleaned = CITE_RE.sub("", value)
        cleaned = TAG_RE.sub("", cleaned)
        return re.sub(r"\s{2,}", " ", cleaned).strip()
    if isinstance(value, list):
        return [strip_markup(v) for v in value]
    if isinstance(value, dict):
        return {k: strip_markup(v) for k, v in value.items()}
    return value


def research(topic):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    messages = [{"role": "user", "content": f"الموضوع: {topic}"}]
    searches = 0
    budget = MAX_TOKENS

    system = SYSTEM_PROMPT.format(n=POINTS)
    voice = load_voice()
    if voice:
        samples = "\n".join(f"- {v}" for v in voice[:15])
        system += ("\n\nأمثلة على النبرة المطلوبة — احتذِ بمستواها اللغوي "
                   "وإيقاعها وطريقة مخاطبتها للقارئ. لا تنسخ عباراتها ولا "
                   "تستخدمها كما هي، بل اكتب بنفس الروح عن موضوعك:\n"
                   f"{samples}")
        print(f"    voice: {len(voice)} sample lines from {VOICE_FILE}")

    # pause_turn continuations plus up to one budget retry
    for _ in range(6):
        payload = {
            "model": TOPIC_MODEL,
            "max_tokens": budget,
            "system": system,
            "messages": messages,
            "tools": [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": MAX_SEARCHES,
            }],
        }

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "content-type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"Claude API {exc.code}: {exc.read().decode()[:500]}")

        content = data.get("content", [])
        searches += sum(1 for b in content if b.get("type") == "server_tool_use")

        if data.get("stop_reason") == "pause_turn":
            messages.append({"role": "assistant", "content": content})
            continue

        if data.get("stop_reason") == "max_tokens":
            if budget < 32000:
                budget = min(32000, budget * 2)
                print(f"  ! reply truncated — retrying with max_tokens={budget}")
                messages = [{"role": "user", "content": f"الموضوع: {topic}"}]
                continue
            raise SystemExit(
                "Reply truncated even at 32000 tokens — lower MAX_SEARCHES "
                "or narrow the topic")

        text = "".join(b.get("text", "") for b in content
                       if b.get("type") == "text").strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()

        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise SystemExit(f"No JSON in reply: {text[:300]}")

        print(f"    {searches} web searches used")
        return strip_markup(json.loads(text[start:end + 1]))

    raise SystemExit("Research didn't finish after 4 continuations")


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

def _build_layout(draw, brief, scale, max_w, kw):
    """Measure the whole card before drawing any of it.
    Returns (blocks, total_height) where each block carries its own font."""
    f_title = load_font(int(58 * scale), bold=True)
    f_lead = load_font(int(38 * scale))
    f_head = load_font(int(40 * scale), bold=True)
    f_body = load_font(int(34 * scale))

    lh_title, lh_lead = int(78 * scale), int(62 * scale)
    lh_head, lh_body = int(58 * scale), int(56 * scale)

    blocks, height = [], 0

    def add(kind, text, font, line_h, fill, indent, first=False):
        nonlocal height
        blocks.append({"kind": kind, "text": text, "font": font, "lh": line_h,
                       "fill": fill, "indent": indent, "first": first})
        height += line_h

    for line in _wrap(draw, brief["title"], f_title, max_w, kw):
        add("title", line, f_title, lh_title, TEXT, 0)

    lead = brief.get("lead", "").strip()
    if lead:
        add("gap", "", None, int(34 * scale), None, 0)
        for line in _wrap(draw, lead, f_lead, max_w - 24, kw):
            add("lead", line, f_lead, lh_lead, (255, 236, 170), 24)

    for i, point in enumerate(brief.get("points", [])):
        add("gap", "", None, int((70 if i == 0 else 62) * scale), None, 0)

        first = True
        for line in _wrap(draw, point["heading"], f_head, max_w - 44, kw):
            add("head", line, f_head, lh_head, ACCENT, 44, first)
            first = False

        add("gap", "", None, int(14 * scale), None, 0)
        for line in _wrap(draw, point["text"], f_body, max_w - 44, kw):
            add("body", line, f_body, lh_body, (206, 212, 228), 44)

    return blocks, height


def _draw_hero(img, photo_path):
    """Top-of-card photo, cropped to fill, fading into the background."""
    try:
        photo = Image.open(photo_path).convert("RGB")
    except Exception as exc:
        print(f"  ! couldn't open photo: {exc}")
        return 0

    target_ratio = W / HERO_HEIGHT
    w, h = photo.size
    if w / h > target_ratio:                     # too wide — crop sides
        new_w = int(h * target_ratio)
        photo = photo.crop(((w - new_w) // 2, 0, (w - new_w) // 2 + new_w, h))
    else:                                        # too tall — crop bottom
        new_h = int(w / target_ratio)
        photo = photo.crop((0, 0, w, new_h))
    photo = photo.resize((W, HERO_HEIGHT), Image.LANCZOS)

    # darken overall so the accent bar and kicker stay readable on top
    overlay = Image.new("RGB", (W, HERO_HEIGHT), BG_TOP)
    photo = Image.blend(photo, overlay, 0.38)
    img.paste(photo, (0, 0))

    # fade the bottom third into the card background
    fade_h = 260
    fade = Image.new("L", (1, fade_h))
    for i in range(fade_h):
        fade.putpixel((0, i), int(255 * (i / fade_h) ** 1.4))
    mask = fade.resize((W, fade_h))
    img.paste(Image.new("RGB", (W, fade_h), BG_TOP),
              (0, HERO_HEIGHT - fade_h), mask)
    return HERO_HEIGHT


def render_topic(brief, out_path, photo_path=None, photo_credit=None):
    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)],
                  fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))

    hero = _draw_hero(img, photo_path) if photo_path else 0
    draw = ImageDraw.Draw(img)

    margin = 80
    right = W - margin
    max_w = W - 2 * margin
    _, kw = ar("م")

    TOP = (hero - 40) if hero else 330
    BOTTOM = H - 250
    available = BOTTOM - TOP

    # Shrink to fit. Only drop a point if even the smallest size overflows.
    points = list(brief.get("points", []))[:POINTS]
    scale, blocks = 1.0, None
    while blocks is None:
        trial = dict(brief, points=points)
        for candidate in (1.0, 0.96, 0.92, 0.88):
            trial_blocks, height = _build_layout(draw, trial, candidate, max_w, kw)
            if height <= available:
                scale, blocks = candidate, trial_blocks
                break
        if blocks is None:
            if len(points) > 2:
                points = points[:-1]
                print(f"  ! content too long — trimmed to {len(points)} points")
            else:
                print("  ! content overflows even at minimum size")
                scale, blocks = 0.88, trial_blocks
    if scale < 1.0:
        print(f"  layout scaled to {int(scale * 100)}% to fit")

    def rtl(xy, text, font, fill, anchor="ra"):
        shaped, k = ar(text)
        draw.text(xy, shaped, font=font, fill=fill, anchor=anchor, **k)

    kicker_y = 96 if hero else 200
    draw.rectangle([right - 110, kicker_y, right, kicker_y + 10], fill=ACCENT)
    rtl((right, kicker_y + 46), KICKER,
        load_font(int(32 * scale), bold=True), ACCENT)

    y = TOP
    lead_top = lead_bottom = None
    for block in blocks:
        if block["kind"] == "gap":
            y += block["lh"]
            continue
        if block["kind"] == "lead":
            if lead_top is None:
                lead_top = y - 6
            lead_bottom = y + block["lh"] - 14
        if block["kind"] == "head" and block["first"]:
            r = max(5, int(7 * scale))
            draw.ellipse([right - 18, y + int(16 * scale),
                          right - 18 + 2 * r, y + int(16 * scale) + 2 * r],
                         fill=ACCENT)
        rtl((right - block["indent"], y), block["text"], block["font"], block["fill"])
        y += block["lh"]

    if lead_top is not None:
        draw.rectangle([right - 6, lead_top, right, lead_bottom], fill=ACCENT)

    f_foot = load_font(28)
    draw.line([(margin, H - 200), (right, H - 200)], fill=(58, 66, 90), width=2)

    # drop sources until the line fits, rather than letting it run off the edge
    names = list(brief.get("sources", []))[:4]
    credit_w = draw.textlength(ar(f"الصورة: {photo_credit}")[0], font=f_foot, **kw) \
        if photo_credit else 0
    room = max_w - credit_w - 40
    while names:
        label = f"المصادر: {'، '.join(names)}"
        if draw.textlength(ar(label)[0], font=f_foot, **kw) <= room or len(names) == 1:
            break
        names.pop()
    label = f"المصادر: {'، '.join(names)}"
    while names and draw.textlength(ar(label)[0], font=f_foot, **kw) > room:
        names[0] = names[0][:-4] + "..."       # last resort: shorten the name
        label = f"المصادر: {'، '.join(names)}"
        if len(names[0]) <= 8:
            break

    rtl((right, H - 155), label, f_foot, MUTED)
    if photo_credit:
        rtl((margin, H - 155), f"الصورة: {photo_credit}", f_foot, MUTED,
            anchor="la")

    img.save(out_path, "PNG", optimize=True)
    return out_path


# --------------------------------------------------------------------------

def main():
    topic = TOPIC or choose_topic()
    if not topic:
        raise SystemExit(f"No topic given and none found in {TOPICS_FILE}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"1/3 researching: {topic}")
    brief = research(topic)
    print(f"    {brief['title']}")
    warn_about_bare_numbers(brief)
    for p in brief["points"]:
        print(f"    • {p['heading']}")

    print("2/3 rendering card...")
    slug = re.sub(r"[^\w]+", "-", topic, flags=re.UNICODE)[:40].strip("-")
    stamp = datetime.now().strftime("%Y-%m-%d")
    queries = brief.get("image_queries", [])
    hero = OUT_DIR / "hero.jpg"
    photo, credit = None, None

    if IMAGE_SOURCE == "article":
        photo, domain = fetch_article_photo(brief.get("source_url", ""), hero)
        if domain:
            credit = DOMAIN_CREDITS.get(domain, domain)
    elif IMAGE_SOURCE == "stock":
        photo = fetch_photo(queries, hero)
        credit = "Pexels" if photo else None
    elif IMAGE_SOURCE == "openverse":
        photo, credit = fetch_openverse_photo(queries, hero)

    # cascade through the remaining sources rather than giving up
    if photo is None and IMAGE_SOURCE != "none":
        if IMAGE_SOURCE != "openverse":
            photo, credit = fetch_openverse_photo(queries, hero)
        if photo is None and IMAGE_SOURCE != "article":
            print("    falling back to the article photo...")
            photo, domain = fetch_article_photo(brief.get("source_url", ""), hero)
            credit = DOMAIN_CREDITS.get(domain, domain) if domain else None
        if photo is None and PEXELS_API_KEY and IMAGE_SOURCE != "stock":
            print("    falling back to Pexels...")
            photo = fetch_photo(queries, hero)
            credit = "Pexels" if photo else None
        if photo is None:
            print("  ! no photo from any source — card will be text only")

    card = render_topic(brief, OUT_DIR / f"{stamp}-{slug}.png", photo, credit)

    if DRY_RUN:
        print(f"3/3 DRY_RUN — nothing posted. Card at {Path(card).resolve()}")
        return

    print("3/3 posting to Snapchat...")
    url = publish_via_github(card) if MEDIA_MODE == "github" else upload_media(card)
    print(f"    media: {url}")
    response = post_story(brief.get("caption", topic), [url])
    print("   ", response)

    if str(response.get("status", "")).lower() != "error":
        used_file = save_used(load_used(), topic)
        commit_and_push(used_file, f"topic: {slug}")


if __name__ == "__main__":
    main()
